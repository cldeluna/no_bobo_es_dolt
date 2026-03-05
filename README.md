 # Don't be a bobo! be a Dolt!

Companion Repository (no_bobo_es_dolt) for [The Gratuitous Arp Don't be a Bobo, be a Dolt](https://gratuitous-arp.net/no-bobo-es-dolt-git-version-control-mysql-database/)


 It includes:
 - `dolt_manage.py` and helper scripts for managing a Dolt SQL database
 - Example CSV data used by the workflow
 - Step-by-step markdown guides for setup, automation, and TLS

 ## Start here

 - **Easy start (get the database running)**

   Follow: [`DOLT_DB_EASY_START.md`](DOLT_DB_EASY_START.md)

   Video: [Setting up the server / Dolt DB Easy Start](https://vimeo.com/1170444154?fl=ml&fe=ec)(~13min)

   This guide walks you through installing Dolt, creating a `config.yml`, starting `dolt sql-server`, creating a database/table, inserting sample data, and making your first Dolt commit.

 - **Python workflow (manage the Dolt database with a script)**

   Follow: [`DOLT_DB_PYWORKFLOW.md`](DOLT_DB_PYWORKFLOW.md)

   Video: [Creating your Database and loading the data / Dolt DB Python Workflow for loading and manipulating data](https://vimeo.com/1170444200?fl=ml&fe=ec) (~20min)
   This video walks you through using `dolt_manage.py` (optionally with `uv`) to load/modify data from CSV, generate commits, and demonstrate recovery with Dolt revision control.

- **Dolt SQL CLI and a Branch Workflow**

	Follow: [`DOLT_DB_PYWORKFLOW.md`](DOLT_DB_PYWORKFLOW.md)

	Video: [A short trip down a branch](https://vimeo.com/1170444295?fl=ml&fe=ec) (~6min)
	This video walks you through the branch/merge workflow.

Supporting Material

 - **Linux client (connect from Ubuntu / install MySQL client)**

   Follow: [`DOLT_LINUX_CLIENT.md`](DOLT_LINUX_CLIENT.md)

   Video: [Linux client out take](https://vimeo.com/1170692593?fl=ml&fe=ec) (~5min)

 - **Encryption / TLS (secure connections to Dolt)**

   Follow: [`DOLT_ENCRYPTION.md`](DOLT_ENCRYPTION.md)

   This guide walks you through generating certificates and configuring Dolt to require secure transport.

   

 ## Blog post draft

 If you want the long-form narrative that accompanies this repo, see:
 - [`no_boboso_es_DOLT.md`](no_boboso_es_DOLT.md)
