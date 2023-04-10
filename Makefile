# Please see Readme.md for for the overall understanding and illustration of these Commands.
basic-setup:
	docker-compose -f common-compose.yml --profile basic-setup -f docker-compose.yml --profile basic-setup up -d --f

basic-setup-with-cost:
	docker-compose -f common-compose.yml --profile basic-setup -f docker-compose.yml --profile basic-setup up -d --f
	docker-compose -f docker-compose.yml --profile cost-setup up -d --f

basic-setup-with-nginx:
	docker-compose -f common-compose.yml --profile basic-setup -f docker-compose.yml --profile basic-setup up -d --f
	docker-compose -f common-compose.yml --profile nginx up -d --f

basic-setup-with-nginx-and-fe:
	docker-compose -f common-compose.yml --profile basic-setup -f docker-compose.yml --profile basic-setup up -d --f
	docker-compose -f common-compose.yml --profile frontend up -d --f
	docker-compose -f common-compose.yml --profile nginx up -d --f

basic-setup-with-cost-with-nginx-and-fe:
	docker-compose -f common-compose.yml --profile basic-setup -f docker-compose.yml --profile basic-setup up -d --f
	docker-compose -f docker-compose.yml --profile cost-setup up -d --f
	docker-compose -f common-compose.yml --profile frontend up -d --f
	docker-compose -f common-compose.yml --profile nginx up -d --f

basic-setup-down:
	docker-compose -f common-compose.yml --profile basic-setup -f docker-compose.yml --profile basic-setup down

basic-setup-with-cost-down:
	docker-compose -f common-compose.yml --profile basic-setup -f docker-compose.yml --profile basic-setup down
	docker-compose -f docker-compose.yml --profile cost-setup down

basic-setup-with-nginx-down:
	docker-compose -f common-compose.yml --profile basic-setup -f docker-compose.yml --profile basic-setup down
	docker-compose -f common-compose.yml --profile nginx down

basic-setup-with-nginx-and-fe-down:
	docker-compose -f common-compose.yml --profile basic-setup -f docker-compose.yml --profile basic-setup down
	docker-compose -f common-compose.yml --profile frontend down
	docker-compose -f common-compose.yml --profile nginx down

basic-setup-with-cost-with-nginx-and-fe-down:
	docker-compose -f common-compose.yml --profile basic-setup -f docker-compose.yml --profile basic-setup down
	docker-compose -f docker-compose.yml --profile cost-setup down
	docker-compose -f common-compose.yml --profile frontend down
	docker-compose -f common-compose.yml --profile nginx down

all-cleanup:
	docker system prune --all

image-cleanup:
	docker image prune --all

volume-cleanup:
	docker volume prune --all

network-cleanup:
	docker network prune


.PHONY: basic-setup basic-setup-with-cost basic-setup-with-nginx basic-setup-with-nginx-and-fe basic-setup-with-cost-with-nginx-and-fe basic-setup-down basic-setup-with-cost-down basic-setup-with-nginx-down basic-setup-with-nginx-and-fe-down basic-setup-with-cost-with-nginx-and-fe-down docker-clean-up all-cleanup image-cleanup volume-cleanup network-cleanup
