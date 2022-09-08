#!/bin/sh
kubectl apply -f rabbitmq/rabbitmq-deployment.yaml
kubectl apply -f rabbitmq/rabbitmq-service.yaml

kubectl apply -f rest/rest-server-deployment.yaml
kubectl apply -f rest/rest-server-service.yaml
kubectl apply -f rest/rest-server-ingress.yaml

kubectl apply -f logs/logs-deployment.yaml

kubectl apply -f worker/worker-deployment.yaml

