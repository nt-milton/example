[![Commitizen friendly](https://img.shields.io/badge/commitizen-friendly-brightgreen.svg)](https://commitizen-tools.github.io/commitizen/)


# Laika App

## Developer Set Up

### Configuration

1. In the root folder create the file: _“.local.env”_
2. Get attributes from 1Password / engineering shared / `.local.env template`
3. Add your AWS access keys. Ask kenneth@heylaika.com for your aws access keys.
4. Only for Mac Apple Silicon (M1, M2, etc...)
    1. Please use the Multistage image available. In your Dockerfile use:
   ```FROM ghcr.io/heylaika/laika-app-img/laika-app-img:m1```
    2. In your docker-compose file, use the document-server latest image for 
       ARM 
       architectures: 
   ```image: onlyoffice/documentserver-de:latest-arm64```
    3. 

### VirtualEnv

1. Install VirtualEnv
    1. `pip3 install virtualenv`
2. Create VirtualEnv
    1. cd to laika-app directory
    2. Run `virtualenv -p python3 .env`
3. Activate VirtualEnv
    1. `source .env/bin/activate`
4. Get Dependencies
    1. `pip install -r requirements.txt`
5. Configure Pycharm IDE
    1. https://docs.google.com/document/d/1lm71lnZb4VSFD0FLlflmMwNO8vxzHUjFTfKt0ahEZ70/

### Pre-Commit and Hooks

1. Activate VirtualEnv
2. Pre-Commit should have been installed as part of the VirtualEnv requirements
    1. Test with command:`pre-commit --version`
    2. If not installed run: `pip install pre-commit`
3. Install the Hooks from _".pre-commit-config.yaml"_:
    1. `pre-commit install`
4. To test the hooks run: `pre-commit run --all-files`

## Running

1. Install Docker
2. Execute `docker compose up` in the project directory
    * `docker compose up -d` to avoid locking the shell

# Relevant docker commands

1. To stop images and not delete containers in the project directory execute 
   `docker compose stop`
2. To delete the containers `docker compose down`
3. To visualize all `docker ps`

## Migration

1. Execute `docker compose run laika-app python3 manage.py migrate` in the 
   project directory

## Only Office

Error codes on commands (Forcesave)
<https://api.onlyoffice.com/editors/command>

## Test

Running pytest in your virtualenv

```
# Run all test cases
env $(cat .local.env  | xargs) pytest

# Run a specific test
env $(cat .local.env  | xargs) pytest monitor/tests/functional_tests.py -k 'test_duplicate_organization_monitor_view'

# Run app test cases
env $(cat .local.env  | xargs) pytest control

# Run all app test cases independently and in parallel (greping only failed)
ls | xargs -P15 -I{} env $(cat .local.env  | xargs) pytest {} | grep failed,
``` 

## Adding flags to Laika Admin

1. Enter into Laika admin `http://localhost:8000/admin/`
2. Navigate to organization
3. Click on Laika dev
4. Enter to 1password find Django Development Admin click on website
5. Copy feature flags located in organization laika-dev into your local admin

## Create a new user to login in laika web locally/develop/staging

[Add Laika Web User From Seeder](https://www.notion.so/heylaika/Seed-Local-User-for-Development-5979755693d34bd9a0dc6b94d4bdd268)

[Add Laika Web User From Django](https://www.notion.so/heylaika/Invite-a-Laika-Web-user-878a17a392e840879e7d63e847adeda8)


### Makefile usage examples
```
make lint
make test
make docker-up
make docker-logs
make docker bash
make test ARGS=controls
make test ARGS=alert/tests/test_utils.py
make test ARGS='monitor/tests/functional_tests.py -k test_duplicate_organization_monitor_view'
make docker-migrations ARGS='organization --name custom_name --empty'
```

## Install Snyk plugin

See installation instructions [here](https://www.notion.so/heylaika/Snyk-plugin-installation-8159b8d2d006481aab84e350147c29c7)

## Commiting to this repo

We follow the [conventional commits spec](https://www.conventionalcommits.org/en/v1.0.0/#summary). To enforce this, we run the commitizen hook on every commit.

The commitizen CLI is also available to ease the transition. Instead of using `git commit -m "your commit message"`, you can run `cz commit` and it will launch an interactive menu that helps you to make sure your commit message adheres to the spec.

More info on [writing commits](https://commitizen-tools.github.io/commitizen/tutorials/writing_commits/)

## FAQ

1. What to do if the app or tests doesn't run?
    * If you're running the site with docker, run:
      `docker compose up --build laika-app`
    * If you're running the site locally, run:
      `pip3 install -r requirements.txt`
    * Common errors:
        * `TypeError: apifun() got an unexpected keyword argument 'databases'`
    * Troubleshooting notion page:
      * https://www.notion.so/heylaika/Backend-324810211c004573819d2a307ee912bd
