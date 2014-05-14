#!/bin/bash

ssh $SSH_VERBOSE -i $GIT_SSH_KEY -o GlobalKnownHostsFile=$SSH_KNOWN_HOSTS -o PasswordAuthentication=no -p $SSH_PORT $1 $2