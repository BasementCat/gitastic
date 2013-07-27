# gitastic

git-centric project management

## Testing

In the root directory, run "python setup.py test" to run all tests in tests/.  Some
prerequisite packages must be installed on your system:
- OpenSSH-Server
- Git
The tests for gitastic-shell start a new sshd with the provided testing keys.