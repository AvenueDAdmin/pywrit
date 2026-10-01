"""Shell execution regression fixture."""

import os
import subprocess


def run_shell_command(cmd):
    subprocess.run(cmd, shell=True, check=True)


def popen_shell_command(cmd):
    subprocess.Popen(cmd, shell=True)


def os_system(cmd):
    os.system(cmd)


def os_popen(cmd):
    os.popen(cmd)


def ssh_exec_command(ssh, cmd):
    ssh.exec_command(cmd)
