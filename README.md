# gitastic

git-centric project management

## Testing

In the root directory, run "python setup.py test" to run all tests in tests/.  Some
prerequisite packages must be installed on your system:
- OpenSSH-Server
- Git
The tests for gitastic-shell start a new sshd with the provided testing keys.

## Database Versioning

For each database (supported are mysql, postgres, and sqlite), create a file in
gitastic/schema named for the database as spelled above.  The file should define only
a dict named "schema" where each key is a schema version (int) and its value is a
SINGLE database operation.  Run gitastic/bin/update-db to update the database to the
latest version, you may specify a database URI as understood by Storm as the first
argument.