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

class TestShell(unittest.TestCase):
	def setUp(self):
		self.sshd=subprocess.check_output("which sshd", shell=True).strip()
		self.ssh_path=os.path.join(os.path.dirname(__file__), "ssh")
		self.host_key=os.path.join(self.ssh_path, "TESTING_ONLY_host_rsa")
		self.client_keys=[
			{"keyfile": "TESTING_ONLY_client_rsa", "valid": True, "userid": 74},
			{"keyfile": "TESTING_ONLY_client_rsa_2", "valid": True, "userid": 96},
			{"keyfile": "TESTING_ONLY_client_rsa_invalid", "valid": False, "userid": 0},
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

		#set up authorized_keys so sshd will let users log in
		#also fix permissions for ssh dirs
		self.temp_dir=tempfile.mkdtemp()
		subprocess.check_call(["/bin/chown", "-R", getpass.getuser(), self.temp_dir])
		subprocess.check_call(["/bin/chmod", "-R", "0700", self.temp_dir])

		self.ssh_home_dir=os.path.join(self.temp_dir, "ssh_temp_home", getpass.getuser())
		self.ssh_authorized_keys=os.path.join(self.ssh_home_dir, ".ssh", "authorized_keys")
		os.makedirs(os.path.join(self.ssh_home_dir, ".ssh"))
		#generate authorized_keys file
		gitasticshell=os.path.join(os.path.dirname(os.path.dirname(__file__)), "gitastic", "gitastic-shell")
		with open(self.ssh_authorized_keys, "w") as fp_auth:
			for kinfo in self.client_keys:
				if not kinfo["valid"]:
					continue
				with open(os.path.join(self.ssh_path, kinfo["keyfile"]+".pub"), "r") as fp_key:
					keydata=fp_key.readline()
					fp_auth.write("command=\"%s %d\",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty %s\n"%(
						gitasticshell, kinfo["userid"], keydata))
		subprocess.check_call(["/bin/chmod", "0600", self.ssh_authorized_keys])
		#later we set this path as $HOME

		#set up path for known_hosts
		self.known_hosts_file=os.path.join(self.temp_dir, "ssh_known_hosts")

		#init a git repo to clone
		self.repo_dir=os.path.join(self.temp_dir, "gitsrc")
		self.repo_init_dir=os.path.join(self.temp_dir, "gitinit")
		self.repo_clone_dir=os.path.join(self.temp_dir, "gitclone")
		os.mkdir(self.repo_dir)
		os.mkdir(self.repo_init_dir)
		#don't create the dir into which we clone or git will bail
		subprocess.check_call("git init --bare %s; cd %s; git init; echo \"test\" >test.txt; git add test.txt; git commit -am \".\"; git remote add origin %s; git push -u origin master;"%(
			self.repo_dir, self.repo_init_dir, self.repo_dir), shell=True)

		#setup the environment for commands to be run
		self.shell_env={
			#We change the ssh key frequently so we can't specify it here
			"GIT_SSH": os.path.join(self.ssh_path, "git_ssh_wrapper.sh"),
			"SSH_KNOWN_HOSTS": self.known_hosts_file,
			"SSH_PORT": str(self.sshd_port),
			"HOME": self.ssh_home_dir
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
		self._stop_sshd.set()
		self._sshd_thread.join()
		shutil.rmtree(self.temp_dir)

	def _run_sshd(self):
		sshd_proc=subprocess.Popen([self.sshd, "-D", "-q", "-h", self.host_key, "-f", self.sshd_config, "-p", str(self.sshd_port),
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
		for kinfo in self.client_keys:
			if not kinfo["valid"]:
				continue
			keyfile=os.path.join(self.ssh_path, kinfo["keyfile"])
			self.assertEqual(
				self._shell("git clone $(whoami)@127.0.0.1:%s %s"%(self.repo_dir, self.repo_clone_dir), env={"GIT_SSH_KEY": keyfile}),
				0
				)
			self.assertTrue(os.path.exists(os.path.join(self.repo_clone_dir, "test.txt")))
			with open(os.path.join(self.repo_clone_dir, "test.txt"), "r") as fp:
				self.assertEqual(fp.read().strip(), "test")
			shutil.rmtree(self.repo_clone_dir)

	def test_push(self):
		previous_test_string="test"
		for kinfo in self.client_keys:
			if not kinfo["valid"]:
				continue
			keyfile=os.path.join(self.ssh_path, kinfo["keyfile"])
			self.assertEqual(
				self._shell("git clone $(whoami)@127.0.0.1:%s %s"%(self.repo_dir, self.repo_clone_dir), env={"GIT_SSH_KEY": keyfile}),
				0
				)
			self.assertTrue(os.path.exists(os.path.join(self.repo_clone_dir, "test.txt")))
			with open(os.path.join(self.repo_clone_dir, "test.txt"), "r") as fp:
				self.assertEqual(fp.read().strip(), previous_test_string)
			with open(os.path.join(self.repo_clone_dir, "test.txt"), "w") as fp:
				previous_test_string="testing_key_%s"%(str(kinfo['userid']),)
				fp.write(previous_test_string)
			current_dir=os.getcwd()
			os.chdir(self.repo_clone_dir)
			self.assertEqual(
				self._shell("git commit -am 'test'"),
				0
				)
			self.assertEqual(
				self._shell("git push --all", env={"GIT_SSH_KEY": keyfile}),
				0
				)
			os.chdir(current_dir)
			shutil.rmtree(self.repo_clone_dir)
			self.assertEqual(
				self._shell("git clone $(whoami)@127.0.0.1:%s %s"%(self.repo_dir, self.repo_clone_dir), env={"GIT_SSH_KEY": keyfile}),
				0
				)
			self.assertTrue(os.path.exists(os.path.join(self.repo_clone_dir, "test.txt")))
			with open(os.path.join(self.repo_clone_dir, "test.txt"), "r") as fp:
				self.assertEqual(fp.read().strip(), previous_test_string)
			shutil.rmtree(self.repo_clone_dir)

	def test_clone_invalid_key(self):
		for kinfo in self.client_keys:
			if kinfo["valid"]:
				continue
			keyfile=os.path.join(self.ssh_path, kinfo["keyfile"])
			self.assertEqual(
				self._shell("git clone $(whoami)@127.0.0.1:%s %s"%(self.repo_dir, self.repo_clone_dir), env={"GIT_SSH_KEY": keyfile}),
				128
				)
			self.assertFalse(os.path.exists(self.repo_clone_dir))

if __name__ == '__main__':
    unittest.main()