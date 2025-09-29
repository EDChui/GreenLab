from ProgressManager.Output.OutputProcedure import OutputProcedure as output

import time
import paramiko
from os import getenv, path
from dotenv import load_dotenv
from scp import SCPClient
load_dotenv()

class ExternalMachineAPI:
    """
    API to interact with external machine via SSH.
    This code is adapted from: https://github.com/S2-group/python-compilers-rep-pkg
    """
    def __init__(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        self.stdin = None
        self.stdout = None
        self.stderr = None
        
        try:
            self.ssh.connect(
                hostname=getenv("GL3_HOSTNAME"),
                key_filename=path.expanduser(getenv("GL3_KEY_PATH")),
            )
            self.ssh.get_transport().set_keepalive(30)
        except paramiko.SSHException:
            output.console_log_FAIL('Failed to send run command to machine!')
            
    def execute_remote_command(self, command : str = '', env : dict = {}, overwrite_channels : bool = True):
        try:
            # Execute the command
            if overwrite_channels:
                self.stdin, self.stdout, self.stderr = self.ssh.exec_command(command,environment=env)
            else:
                self.ssh.exec_command(command,environment=env, timeout=4200)
        except paramiko.SSHException:
            output.console_log_FAIL('Failed to send run command to machine.')
        except TimeoutError:
            output.console_log_FAIL('Timeout reached while waiting for command output.')

    def copy_file_from_remote(self, remote_path, local_path):
        # Create SSH client and SCP client
        with SCPClient(self.ssh.get_transport()) as scp:
            # Copy the file from remote to local
            scp.get(remote_path, local_path, recursive=True)
        output.console_log_OK(f"Copied {remote_path} to {local_path}")

    def read_line_indefinitely(self):
        buffer = ""
        while True:
            char = self.stdout.read(1).decode('utf-8')  # Read one byte at a time
            if char:  # If data is received
                buffer += char
                if '\n' in buffer:  # Check if a full line has been read
                    line, buffer = buffer.split('\n', 1)
                    return line.strip()
            else:
                # Check if the stream is closed
                if self.stdout.channel.exit_status_ready():
                    break
                # Optional: Add a small sleep to avoid busy loop
                time.sleep(0.1)

        # If we exit the loop, no more data will be received
        return None

    def __del__(self):
        self.stdin.close()
        self.stdout.close()
        self.stderr.close()
        self.ssh.close()

if __name__ == "__main__":
    ssh = ExternalMachineAPI()
    ssh.execute_remote_command("echo Hello, World!")
    print(ssh.stdout.readline())
    del ssh
