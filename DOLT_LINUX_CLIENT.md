
# Setting up the Linux Dolt Client


Installed OrbStack on Mac.  This is a Mac only option. 

```
brew update
brew install --cask orbstack
```

Using Orb GUI, created an ubuntu vm

These steps install the MySQL 8 client on Ubuntu using the official MySQL APT repository.

They add the MySQL repo (essential for MySQL 8.x, as Ubuntu's default may offer older or MariaDB), allow version selection via `dpkg-reconfigure`, and install the client. The `mysql-client=8.4*` step pins to 8.4 specifically, which works if available post-config; otherwise, the final `sudo apt install mysql-client` grabs the repo's latest MySQL 8 client.

The `mysql-client=8.4*` install might fail if 8.4 isn't listed yet—run `sudo apt update` after reconfiguration if needed. For client-only (no server), skip any server packages; this script does that correctly.


ssh ubuntu@orb

```bash
claudiadeluna@ubuntu:~$ 
# Check reachability to the Dold server
ping <SERVER_IP>

# Update the local package lists from Ubuntu repositories for latest package info
sudo apt update

# Install net-tools package which provides ifconfig and other classic network utilities
sudo apt install net-tools

# Install wget package for downloading files from the web via command line
sudo apt install wget

# Install gnupg package for handling GPG keys used in package verification
sudo apt install gnupg

# Download the MySQL APT repository configuration package (.deb file)
wget https://dev.mysql.com/get/mysql-apt-config_0.8.34-1_all.deb

# Install the downloaded MySQL APT config package to add MySQL repository to sources.list
sudo dpkg -i mysql-apt-config_0.8.34-1_all.deb

# Attempt to install specific MySQL client version 8.4 (may prompt version selection)
sudo apt install mysql-client=8.4*
# For Ubuntu 22.04, 8.4 will likely not be found so you will need the following two commands

# Reconfigure the MySQL APT repository settings interactively (version/source selection)
sudo dpkg-reconfigure mysql-apt-config

# Install the MySQL client package (uses configured repo, latest compatible version)
sudo apt install mysql-client

# Verify MySQL client installation by checking the installed version
mysql --version

# Install uv (fast Python package & project manager) using the official installation script
curl -LsSf https://astral.sh/uv/install.sh | sh

# To add $HOME/.local/bin to your PATH, either restart your shell or run:
source $HOME/.local/bin/env

# Verify uv installation by checking the installed version (should show current release like 0.4.x)
uv --version

# Install git package for version control (cloning repos, managing Dolt branches, etc.)
# We will need this to clone the repository
sudo apt install git

# Verify git installation by checking the installed version
git --version
```



## You should now have a working client

Now that we have a good working environment, we can remotely access and manage our Dolt database.

```bash
mysql -h <SERVER_IP> -P 3306 -u dbadmin -p
```



