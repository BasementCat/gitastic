import unittest
import sys
import os
import subprocess
import shutil
import glob
import tempfile
from storm.exceptions import IntegrityError
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "gitastic"))

from lib import gitastic, database
gitastic.configDir=os.path.join(os.path.dirname(__file__), "config")
gitastic.init()

class _ModelTestBase(unittest.TestCase):
    def _drop_tables(self):
        database.getStore().execute("SET FOREIGN_KEY_CHECKS = 0;")
        for table in database.getStore().execute("show tables;"):
            database.getStore().execute("drop table %s;"%(table[0],))
        database.getStore().execute("SET FOREIGN_KEY_CHECKS = 1;")

    def setUp(self):
        self._drop_tables()
        subprocess.call([os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gitastic", "update-db"), gitastic.config.get("DatabaseURI")])

    def tearDown(self):
        self._drop_tables()

class TestUserModel(_ModelTestBase):
    def setUp(self):
        super(TestUserModel, self).setUp()

        u=database.User(username=u"user1", email=u"user1@example.com")
        u.setPassword(u"password")
        database.getStore().add(u)
        database.getStore().commit()

    def test_authenticate_invalid_user(self):
        u=database.User.authenticate("nouser", "nopassword")
        self.assertIsNone(u)

    def test_authenticate_invalid_password(self):
        u=database.User.authenticate("user1", "nopassword")
        self.assertIsNone(u)

    def test_authenticate(self):
        u=database.User.authenticate("user1", "password")
        self.assertIsNotNone(u)
        self.assertEqual(u.username, u"user1")

    def test_password_newhash(self):
        u=database.User()
        u.setPassword("password1")
        password1=u.password
        u.setPassword("password1")
        password2=u.password
        self.assertNotEqual(password1, password2)

    def test_username_invalidchars(self):
        with self.assertRaises(database.ValidationError):
            database.User.validateUsername(u"this has$invalid*chars!")

    def test_username_validchars(self):
        database.User.validateUsername(u"this_has-invalid_chars")

class TestUserSSHKeyModel(_ModelTestBase):
    def setUp(self):
        super(TestUserSSHKeyModel, self).setUp()

        self.pubkeys=[]
        self.privkeys=[]

        for fname in glob.glob(os.path.join(os.path.dirname(__file__), "ssh", "TESTING_ONLY*")):
            if fname.endswith(".pub"):
                self.pubkeys.append(fname)
            else:
                self.privkeys.append(fname)

    def test_valid_keys(self):
        for keyfile in self.pubkeys:
            with open(keyfile, "r") as fp:
                self.assertTrue(database.UserSSHKey.validateKey(fp.read()))

    def test_invalid_keys(self):
        for keyfile in self.privkeys:
            with open(keyfile, "r") as fp:
                self.assertFalse(database.UserSSHKey.validateKey(fp.read()))

    def test_user_keys(self):
        u=database.User(username=u"user", password=u"", email=u"")
        for keyfile in self.pubkeys:
            with open(keyfile, "r") as fp:
                u.keys.add(database.UserSSHKey(name=unicode(keyfile), key=unicode(fp.read())))
        database.getStore().add(u)
        database.getStore().commit()
        del u
        u=database.getStore().find(database.User).one()
        self.assertIsNotNone(u)
        self.assertEqual(u.keys.count(), len(self.pubkeys))

class TestRepositoryModel(_ModelTestBase):
    def setUp(self):
        super(TestRepositoryModel, self).setUp()

        self.repobase=tempfile.mkdtemp()
        self.repoclonedir=tempfile.mkdtemp()
        gitastic.config.configuration=gitastic.config._merged(gitastic.config.configuration, {"Repository": {"BaseDirectory": self.repobase}})

        self.repouser=database.User(username=u"Tester", email=u"tester@example.com", password=u"")
        database.getStore().add(self.repouser)
        database.getStore().commit()

    def tearDown(self):
        super(TestRepositoryModel, self).tearDown()

        shutil.rmtree(self.repobase)
        shutil.rmtree(self.repoclonedir)

    def test_create_repo(self):
        repo=database.Repository(name=u"test-repo", description=u"Testing Repo")
        self.repouser.repositories.add(repo)
        repo.setPath()
        database.getStore().commit()
        repo.create()
        self.assertTrue(os.path.exists(repo.getRepositoryDir()))
        self.assertEqual(repo.path, unicode(u"/".join((repo.getOwnerName(), repo.name))))

    def test_create_repo_readme(self):
        repo=database.Repository(name=u"test-repo", description=u"Testing Repo")
        self.repouser.repositories.add(repo)
        repo.setPath()
        database.getStore().commit()
        repo.create(add_readme=True)
        self.assertTrue(os.path.exists(repo.getRepositoryDir()))
        curdir=os.getcwd()
        os.chdir(self.repoclonedir)
        try:
            subprocess.check_call([gitastic.config.get("Repository/Git", do_except=True), "clone", repo.getRepositoryDir(), repo.getRepositoryDir().split("/").pop()])
            readme=os.path.join(self.repoclonedir, repo.getRepositoryDir().split("/").pop(), "README.md")
            self.assertTrue(os.path.exists(os.path.dirname(readme)))
            self.assertTrue(os.path.exists(readme))
            with open(readme, "r") as fp:
                self.assertEqual(fp.read(), "# test-repo\n\nTesting Repo\n")
        finally:
            os.chdir(curdir)

    def test_create_duplicate(self):
        repo1=database.Repository(name=u"test-repo", description=u"Testing Repo")
        self.repouser.repositories.add(repo1)
        repo1.setPath()
        database.getStore().commit()
        repo1.create()
        with self.assertRaises(IntegrityError):
            repo2=database.Repository(name=u"test-repo", description=u"Testing Repo")
            self.repouser.repositories.add(repo2)
            repo2.setPath()
            database.getStore().commit()
        repo3=database.Repository(name=u"test-repo3", description=u"Testing Repo")
        self.repouser.repositories.add(repo3)
        repo3.setPath()
        os.makedirs(repo3.getRepositoryDir())
        with self.assertRaises(database.RepositoryError):
            repo3.create()
        database.getStore().rollback()

    def test_name_invalidchars(self):
        with self.assertRaises(database.ValidationError):
            database.Repository.validateName(u"this has$invalid*chars!")

    def test_name_validchars(self):
        database.Repository.validateName(u"this_has-invalid_chars")

class TestRepositoryAccessModel(_ModelTestBase):
    def setUp(self):
        super(TestRepositoryAccessModel, self).setUp()
        self.repo_owner=database.User(username=u"Tester", email=u"tester@example.com", password=u"")
        self.repo_user=database.User(username=u"Tester2", email=u"tester2@example.com", password=u"")
        self.repo=database.Repository(name=u"test-repo", description=u"Testing repo", public=False)
        self.repo_owner.repositories.add(self.repo)
        database.getStore().add(self.repo_owner)
        database.getStore().add(self.repo_user)
        database.getStore().add(self.repo)
        database.getStore().commit()

    def test_ACC_OWNER(self):
        self.assertEqual(self.repo.getAccess(self.repo_owner), database.Repository.ACC_OWNER)
        self.assertTrue(self.repo.getAccess(self.repo_owner)&database.Repository.PERM_ADMIN)
        self.assertTrue(self.repo.getAccess(self.repo_owner)&database.Repository.PERM_PUSH)
        self.assertTrue(self.repo.getAccess(self.repo_owner)&database.Repository.PERM_CLONE)
        self.assertTrue(self.repo.getAccess(self.repo_owner)&database.Repository.PERM_VIEW)
        self.assertEqual(self.repo.getAccess(self.repo_user), database.Repository.ACC_NONE)
        with self.assertRaises(database.RepositoryError):
            self.repo.setAccess(self.repo_user, database.Repository.ACC_OWNER)

    def test_ACC_ADMIN(self):
        self.repo.setAccess(self.repo_user, database.Repository.ACC_ADMIN)
        self.assertEqual(self.repo.getAccess(self.repo_user), database.Repository.ACC_ADMIN)
        self.assertTrue(self.repo.getAccess(self.repo_user)&database.Repository.PERM_ADMIN)
        self.assertTrue(self.repo.getAccess(self.repo_user)&database.Repository.PERM_PUSH)
        self.assertTrue(self.repo.getAccess(self.repo_user)&database.Repository.PERM_CLONE)
        self.assertTrue(self.repo.getAccess(self.repo_user)&database.Repository.PERM_VIEW)

    def test_ACC_PUSH(self):
        self.repo.setAccess(self.repo_user, database.Repository.ACC_PUSH)
        self.assertEqual(self.repo.getAccess(self.repo_user), database.Repository.ACC_PUSH)
        self.assertFalse(self.repo.getAccess(self.repo_user)&database.Repository.PERM_ADMIN)
        self.assertTrue(self.repo.getAccess(self.repo_user)&database.Repository.PERM_PUSH)
        self.assertTrue(self.repo.getAccess(self.repo_user)&database.Repository.PERM_CLONE)
        self.assertTrue(self.repo.getAccess(self.repo_user)&database.Repository.PERM_VIEW)

    def test_ACC_VIEW(self):
        self.repo.setAccess(self.repo_user, database.Repository.ACC_VIEW)
        self.assertEqual(self.repo.getAccess(self.repo_user), database.Repository.ACC_VIEW)
        self.assertFalse(self.repo.getAccess(self.repo_user)&database.Repository.PERM_ADMIN)
        self.assertFalse(self.repo.getAccess(self.repo_user)&database.Repository.PERM_PUSH)
        self.assertTrue(self.repo.getAccess(self.repo_user)&database.Repository.PERM_CLONE)
        self.assertTrue(self.repo.getAccess(self.repo_user)&database.Repository.PERM_VIEW)

    def test_ACC_NONE(self):
        self.repo.setAccess(self.repo_user, database.Repository.ACC_NONE)
        self.assertEqual(self.repo.getAccess(self.repo_user), database.Repository.ACC_NONE)
        self.assertFalse(self.repo.getAccess(self.repo_user)&database.Repository.PERM_ADMIN)
        self.assertFalse(self.repo.getAccess(self.repo_user)&database.Repository.PERM_PUSH)
        self.assertFalse(self.repo.getAccess(self.repo_user)&database.Repository.PERM_CLONE)
        self.assertFalse(self.repo.getAccess(self.repo_user)&database.Repository.PERM_VIEW)

        self.repo.public=True
        self.assertFalse(self.repo.getAccess(self.repo_user)&database.Repository.PERM_ADMIN)
        self.assertFalse(self.repo.getAccess(self.repo_user)&database.Repository.PERM_PUSH)
        self.assertTrue(self.repo.getAccess(self.repo_user)&database.Repository.PERM_CLONE)
        self.assertTrue(self.repo.getAccess(self.repo_user)&database.Repository.PERM_VIEW)

    def test_invalid_level(self):
        with self.assertRaises(database.RepositoryError):
            self.repo.setAccess(self.repo_user, 173)

if __name__ == '__main__':
    unittest.main()