import unittest
import sys
import os
import subprocess
import glob
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "gitastic"))

from lib import gitastic, database
gitastic.configDir=os.path.join(os.path.dirname(__file__), "config")
gitastic.init()

class _ModelTestBase(unittest.TestCase):
    def _drop_tables(self):
        for table in database.getStore().execute("show tables;"):
            database.getStore().execute("drop table %s;"%(table[0],))

    def setUp(self):
        self._drop_tables()
        subprocess.call([os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "gitastic", "update-db")),
            gitastic.config.get("DatabaseURI")])

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

if __name__ == '__main__':
    unittest.main()