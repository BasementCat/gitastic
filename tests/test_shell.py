import sys
import os
import unittest
import subprocess
import threading
import socket
import time
import tempfile
import shutil
import copy
import getpass
import signal
import yaml
from storm.tracer import debug as storm_query_debug

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "gitastic"))
from lib import gitastic, database
gitastic.configDir=os.path.join(os.path.dirname(__file__), "config")
gitastic.init()

class TestShell(unittest.TestCase):
    #Set this to True for extra SSH debugging
    ssh_debug=False
    #Set this to True for query debugging
    query_debug=False

    def __init__(self, *args, **kwargs):
        if self.query_debug:
            storm_query_debug(True, stream=sys.stderr)
        super(TestShell, self).__init__(*args, **kwargs)

    def _drop_tables(self):
        database.getStore().execute("SET FOREIGN_KEY_CHECKS = 0;")
        for table in database.getStore().execute("show tables;"):
            database.getStore().execute("drop table %s;"%(table[0],))
        database.getStore().execute("SET FOREIGN_KEY_CHECKS = 1;")

    def setUp(self):
        #init the database
        self._drop_tables()
        subprocess.call([os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "gitastic", "update-db")),
            gitastic.config.get("DatabaseURI")])

        #init paths
        self.sshd=subprocess.check_output("which sshd", shell=True).strip()
        self.ssh_path=os.path.join(os.path.abspath(os.path.dirname(__file__)), "ssh")
        self.host_key=os.path.join(self.ssh_path, "TESTING_ONLY_host_rsa")
        self.client_keys=[
            {"keyfile": "TESTING_ONLY_client_rsa", "valid": True},
            {"keyfile": "TESTING_ONLY_client_rsa_2", "valid": True},
            {"keyfile": "TESTING_ONLY_client_rsa_invalid", "valid": False},
        ]
        self.sshd_config=os.path.join(self.ssh_path, "sshd_config")
        #find a port on this machine that is not in use for the sshd
        self.sshd_port=None
        for candidatePort in range(2000, 3000):
            s=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            res=s.connect_ex(("127.0.0.1", candidatePort))
            if res==0:
                s.close()
                continue
            self.sshd_port=candidatePort
            break
        #sanity checks - we have to have an sshd and keys for testing
        self.assertNotEqual(self.sshd, "", "Missing SSHD (ensure 'which sshd' returns something)")
        self.assertTrue(os.path.isfile(self.host_key), "Missing host key at %s"%(self.host_key,))
        self.assertTrue(os.path.isfile(self.host_key+".pub"), "Missing host pubkey at %s"%(self.host_key+".pub",))
        self.assertIsNotNone(self.sshd_port, "Could not find suitable port to start SSHD on")

        #Set up a temp dir to hold everything (makes for easy cleanup)
        self.temp_dir=tempfile.mkdtemp()

        #Write out an alternate configuration
        self.config_dir=os.path.join(self.temp_dir, "config")
        os.makedirs(self.config_dir)
        subprocess.check_call("cp -rf %s/* %s/"%(os.path.join(os.path.dirname(__file__), "config"), self.config_dir), shell=True)
        with open(os.path.join(self.config_dir, "testing_config.yml"), "w") as fp:
            fp.write(yaml.dump({"Repository": {"BaseDirectory": self.temp_dir}}))
        gitastic.config.load(os.path.join(self.config_dir, "testing_config.yml"))
        
        #fix permissions for ssh dirs
        subprocess.check_call(["/bin/chown", "-R", getpass.getuser(), self.temp_dir])
        subprocess.check_call(["/bin/chmod", "-R", "0700", self.temp_dir])

        #set up authorized_keys so sshd will let users log in
        self.ssh_home_dir=os.path.join(self.temp_dir, "ssh_temp_home", getpass.getuser())
        self.ssh_authorized_keys=os.path.join(self.ssh_home_dir, ".ssh", "authorized_keys")
        os.makedirs(os.path.join(self.ssh_home_dir, ".ssh"))
        
        #generate authorized_keys file
        self.keyfile_map={}
        gitasticshell=os.path.join(os.path.dirname(os.path.abspath(os.path.dirname(__file__))), "gitastic", "gitastic-shell")
        with open(self.ssh_authorized_keys, "w") as fp_auth:
            for i, kinfo in enumerate(self.client_keys):
                if not kinfo["valid"]:
                    continue
                with open(os.path.join(self.ssh_path, kinfo["keyfile"]+".pub"), "r") as fp_key:
                    keydata=fp_key.readline()
                    #To get a valid key ID we need to add it to the db
                    u=database.User(username=u"%s_%d"%(keydata.split().pop(), i), email=u"user@example.com", password=u".")
                    k=database.UserSSHKey(user=u, name=unicode(keydata.split().pop()), key=unicode(keydata))
                    database.getStore().add(u)
                    database.getStore().add(k)
                    database.getStore().commit()
                    self.keyfile_map[k.user_ssh_key_id]=os.path.join(self.ssh_path, kinfo["keyfile"])
                    fp_auth.write("command=\"%s %d %s\",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty %s\n"%(
                        gitasticshell, k.user_ssh_key_id, self.config_dir, keydata))
        subprocess.check_call(["/bin/chmod", "0600", self.ssh_authorized_keys])
        #later we set this path as $HOME

        #set up path for known_hosts
        self.known_hosts_file=os.path.join(self.temp_dir, "ssh_known_hosts")

        #init a git repo to clone
        self.repo_clone_dir=os.path.join(self.temp_dir, "gitclone")
        #don't create the dir into which we clone or git will bail
        self.assertFalse(os.path.exists(self.repo_clone_dir))

        #we'll create the same repo for each user
        for u in database.getStore().find(database.User):
            r=database.Repository(name=u"test_repo", description=u"This is a testing repository")
            u.repositories.add(r)
            r.setPath()
            r.create(add_readme=True)
        database.getStore().commit()

        #setup the environment for commands to be run
        self.shell_env={
            #We change the ssh key frequently so we can't specify it here
            "GIT_SSH": os.path.join(self.ssh_path, "git_ssh_wrapper.sh"),
            "SSH_KNOWN_HOSTS": self.known_hosts_file,
            "SSH_PORT": str(self.sshd_port),
            "HOME": self.ssh_home_dir,
            "SSH_VERBOSE": "-v -v -v" if self.ssh_debug else ""
        }

        #start up the sshd
        self._stop_sshd=threading.Event()
        self._sshd_thread=threading.Thread(target=self._run_sshd)
        self._sshd_thread.start()
        #let the sshd start up
        time.sleep(1)
        
        #now make sure the sshd is accepting connections or we can't keep testing
        s=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        res=s.connect_ex(("127.0.0.1", self.sshd_port))
        s.close()
        self.assertEqual(res, 0, "The test SSHD is not accepting connections")
        
        #Generate known_hosts from the ssh server we just started
        with open(self.known_hosts_file, "w") as fp:
            for line in subprocess.check_output("ssh-keyscan -H -t rsa -p %d 127.0.0.1"%(self.sshd_port,), shell=True).split("\n"):
                if line.startswith("#"):
                    continue
                fp.write(line)
                fp.write("\n")

    def tearDown(self):
        self._drop_tables()
        self._stop_sshd.set()
        self._sshd_thread.join()
        shutil.rmtree(self.temp_dir)

    def _run_sshd(self):
        sshd_proc=subprocess.Popen([self.sshd, "-D", ("-e" if self.ssh_debug else "-q"), "-h", self.host_key, "-f", self.sshd_config, "-p", str(self.sshd_port),
            "-o", "AuthorizedKeysFile=%s"%(self.ssh_authorized_keys,), "-o", "StrictModes=no"], stdout=sys.stderr, stderr=sys.stderr, env=self.shell_env)
        pid=sshd_proc.pid
        self._stop_sshd.wait()
        sshd_proc.terminate()
        try:
            os.kill(int(pid), signal.SIGTERM)
            os.kill(int(pid), signal.SIGKILL)
        except OSError:
            pass

    def _shell(self, *args, **kwargs):
        myenv=copy.deepcopy(self.shell_env)
        mykwargs=copy.deepcopy(kwargs)
        if "env" in mykwargs:
            myenv.update(mykwargs["env"])
        mykwargs["env"]=myenv
        proc=subprocess.Popen(*args, shell=True, **mykwargs)
        return proc.wait()

    def test_clone(self):
        users=database.getStore().find(database.User)
        self.assertGreater(users.count(), 0)
        for u in users:
            self.assertGreater(u.keys.count(), 0)
            self.assertGreater(u.repositories.count(), 0)
            key=None
            for _key in u.keys:
                key=_key
                break
            keyfile=self.keyfile_map[key.user_ssh_key_id]
            for r in u.repositories:
                clonedir="%s_%d"%(self.repo_clone_dir, r.repository_id)
                self.assertEqual(
                    self._shell("git clone %s %s"%(r.getRepositoryCloneURI(), clonedir), env={"GIT_SSH_KEY": keyfile}),
                    0
                    )
                readme=os.path.join(clonedir, "README.md")
                self.assertTrue(os.path.exists(os.path.dirname(readme)))
                self.assertTrue(os.path.exists(readme))
                with open(readme, "r") as fp:
                    self.assertEqual(fp.read(), "# %s\n\n%s\n"%(r.name, r.description))
                shutil.rmtree(clonedir)

    def test_push(self):
        users=database.getStore().find(database.User)
        self.assertGreater(users.count(), 0)
        for u in users:
            self.assertGreater(u.keys.count(), 0)
            self.assertGreater(u.repositories.count(), 0)
            key=None
            for _key in u.keys:
                key=_key
                break
            keyfile=self.keyfile_map[key.user_ssh_key_id]
            for r in u.repositories:
                clonedir="%s_%d"%(self.repo_clone_dir, r.repository_id)

                #clone the repo
                self.assertEqual(
                    self._shell("git clone %s %s"%(r.getRepositoryCloneURI(), clonedir), env={"GIT_SSH_KEY": keyfile}),
                    0
                    )
                readme=os.path.join(clonedir, "README.md")
                self.assertTrue(os.path.exists(os.path.dirname(readme)))
                self.assertTrue(os.path.exists(readme))
                with open(readme, "r") as fp:
                    self.assertEqual(fp.read(), "# %s\n\n%s\n"%(r.name, r.description))

                #make, commit, and push changes
                with open(readme, "a") as fp:
                    fp.write("%s\n"%(r.name,))
                curdir=os.getcwd()
                os.chdir(clonedir)
                self.assertEqual(self._shell("git commit -am \"Test commit\""), 0)
                self.assertEqual(self._shell("git push --all", env={"GIT_SSH_KEY": keyfile}), 0)
                os.chdir(curdir)

                #Remove all traces, re-clone and verify
                shutil.rmtree(clonedir)
                self.assertEqual(
                    self._shell("git clone %s %s"%(r.getRepositoryCloneURI(), clonedir), env={"GIT_SSH_KEY": keyfile}),
                    0
                    )
                readme=os.path.join(clonedir, "README.md")
                self.assertTrue(os.path.exists(os.path.dirname(readme)))
                self.assertTrue(os.path.exists(readme))
                with open(readme, "r") as fp:
                    self.assertEqual(fp.read(), "# %s\n\n%s\n%s\n"%(r.name, r.description, r.name))
                shutil.rmtree(clonedir)

    def test_clone_invalid_key(self):
        users=database.getStore().find(database.User)
        self.assertGreater(users.count(), 0)
        for u in users:
            self.assertGreater(u.repositories.count(), 0)
            for r in u.repositories:
                for kinfo in self.client_keys:
                    if kinfo["valid"]:
                        continue
                    keyfile=os.path.join(self.ssh_path, kinfo["keyfile"])
                    clonedir="%s_%d"%(self.repo_clone_dir, r.repository_id)
                    self.assertEqual(
                        self._shell("git clone %s %s"%(r.getRepositoryCloneURI(), clonedir), env={"GIT_SSH_KEY": keyfile}),
                        128
                        )
                    self.assertFalse(os.path.exists(clonedir))

if __name__ == '__main__':
    unittest.main()