import os
import unittest
import subprocess
import threading
import socket
import time

class TestShell(unittest.TestCase):
	def setUp(self):
		self.sshd=subprocess.check_output("which sshd", shell=True).strip()
		self.ssh_path=os.path.join(os.path.dirname(__file__), "ssh")
		self.host_key=os.path.join(self.ssh_path, "TESTING_ONLY_host_rsa")
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

	def tearDown(self):
		self._stop_sshd.set()
		self._sshd_thread.join()

	def _run_sshd(self):
		sshd_proc=subprocess.Popen([self.sshd, "-q", "-h", self.host_key, "-D", "-f", self.sshd_config, "-p", str(self.sshd_port)])
		self._stop_sshd.wait()
		sshd_proc.terminate()

	def test_nothing(self):
		pass

# class TestSequenceFunctions(unittest.TestCase):

#     def setUp(self):
#         self.seq = range(10)

#     def test_shuffle(self):
#         # make sure the shuffled sequence does not lose any elements
#         random.shuffle(self.seq)
#         self.seq.sort()
#         self.assertEqual(self.seq, range(10))

#         # should raise an exception for an immutable sequence
#         self.assertRaises(TypeError, random.shuffle, (1,2,3))

#     def test_choice(self):
#         element = random.choice(self.seq)
#         self.assertTrue(element in self.seq)

#     def test_sample(self):
#         with self.assertRaises(ValueError):
#             random.sample(self.seq, 20)
#         for element in random.sample(self.seq, 5):
#             self.assertTrue(element in self.seq)

if __name__ == '__main__':
    unittest.main()