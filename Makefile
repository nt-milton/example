# This is useful because sometimes there are user permissions problems with docker
# when creating migrations inside the docker container because it uses a different
# user than the one that the host machine has, this commands works
# for UNIX/OSX operating system. This command should work
# for git bash terminal for windows users, although make should be installed
# and docker works a bit different for windows
USER_ID := $(shell id -u):$(shell id -g)
.DEFAULT_GOAL := help


help: ## Prints this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-10s\033[0m %s\n", $$1, $$2}'

test: ## Run tests by loading .local.env environmental variables
	env $$(cat .local.env | grep -v ^# | xargs) pytest $(ARGS)

migrate: ## Migrate
	python3 manage.py migrate $(ARGS)

migrations: ## Create Migrations
	python3 manage.py makemigrations $(ARGS)

lint: ## Runs pre-commit with all the files
	pre-commit run --all $(ARGS)


# Docker specific commands

docker-up: ## Run docker-compose up in background
	docker compose up -d $(ARGS)

docker-stop: ## Stop all running services in docker-compose
	docker compose stop

docker-restart: ## Restart all running services
	make docker stop
	make docker up

docker-logs: ## Show django backend logs
	docker compose logs --tail 40 -f laika-app

docker-bash: ## Bash into docker container securely with your machine user id
	docker compose exec --user $(USER_ID) laika-app bash

docker-migrate: ## Execute migrate with docker container
	docker compose exec --user $(USER_ID) laika-app make migrate ARGS='$(ARGS)'

docker-migrations: ## Create migrations with the docker container
    docker compose exec --user $(USER_ID) laika-app make migrations ARGS='$ (ARGS)'

docker-test: ## Execute tests with the docker container
	docker compose exec --user $(USER_ID) laika-app make test ARGS='$(ARGS)'
