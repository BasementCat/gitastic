#!/bin/bash

ssh -i $GIT_SSH_KEY -o GlobalKnownHostsFile=$SSH_KNOWN_HOSTS -o PasswordAuthentication=no -p $SSH_PORT -v -v $1 $2