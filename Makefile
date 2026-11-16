.PHONY: install run test lint docker compose k8s tf-plan tf-apply tf-destroy

install:      ## Install dev dependencies
	pip install -r requirements-dev.txt

run:          ## Run the API locally on http://localhost:8000
	uvicorn app.main:app --reload

test:         ## Run the test suite with coverage
	pytest --cov=app --cov-report=term-missing

lint:
	ruff check .

docker:       ## Build and run the container
	docker build -t veriframe:local . && docker run --rm -p 8000:8000 veriframe:local

compose:      ## API + local DynamoDB
	docker compose up --build

k8s:          ## Deploy to a local kind cluster
	kind create cluster --name veriframe || true
	docker build -t veriframe:local .
	kind load docker-image veriframe:local --name veriframe
	kubectl apply -f k8s/veriframe.yaml
	kubectl -n veriframe rollout status deploy/veriframe

tf-plan:
	cd infra/terraform && terraform init && terraform plan

tf-apply:
	cd infra/terraform && terraform init && terraform apply

tf-destroy:   ## Tear everything down (avoid AWS charges)
	cd infra/terraform && terraform destroy
