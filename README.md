# ws-cbs

This branch contains the app together with a Docker deployment setup.

## Docker Deployment

You can deploy the application using:

```bash
docker compose up
```

The application takes a bit until it is fully functional because it does an initial health check of all services, in a sequential manner.

The Authentication service runs on port `5001` and the URL Shortener service runs on port `5000` (although only internally accessible).
We use NGINX as our reverse proxy, therefore their endpoints are:

**Authentication Service**: `//http:localhost/api/auth`
**URL Shortening Service**: `//http:localhost/api/shorten`

## Kubernetes Deployment

You can deploy the application using the following command:

```bash
minikube kubectl -- apply -f k8s_deployments.yaml
```

Given the local scope of MiniKube, you cannot access your containers outside of the machine that the cluster is currently running on.
Therefore, once the application is deployed you need to get the IP of the Ingress Controller like this:

```bash
minikube kubectl -- get ingress -n ws-cbs   
```

Afterwards, you can use the ADDRESS entry of the output in the curl commands available in the Testing section.
Example: _`curl -X POST http://192.168.49.2/api/auth/users -H "Content-Type: application/json" -d '{"username" : "demo", "password" : "demopass"}'`_

This command:
1. Creates the Namespace, Deployments, Services, Persistent Volume Claim (PVC), and Ingress Controller.
2. Ensures Kubernetes schedules the Pods and connects them via Services.

To check the deployment you can use:

```bash
minikube kubectl -- get pods -n ws-cbs # Checks Pods
minikube kubectl -- get svc -n ws-cbs # Checks Services
minikube kubectl -- get ingress -n ws-cbs # Checks ingress controller
minikube kubectl -- get pvc -n ws-cbs # Checks the PVC of the DB
```

To check how requests are distributed to different replicas of the _url\_shortener_ service, we use the logs of our Ingress Controller:
```bash
minikube kubectl -- get endpoints url-shortener -o wide -n ws-cbs # Get url shortener endpoints
minikube kubectl -- logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --follow # Get nginx logs
```

## Testing

### Some CURL Requests
1. **Create User**: 
```bash
curl -X POST http://localhost/api/auth/users -H "Content-Type: application/json" -d '{"username" : "demo", "password" : "demopass"}'
```

2. **Login (Get JWT Token)**: 
```bash
curl -X POST http://localhost/api/auth/users/login -H "Content-Type: application/json" -d '{"username" : "demo", "password" : "demopass"}'
```


### Postman
The application can be tested using the `Postman` configurations present in the respective folder.

Make sure to:
1. Import both the Collection and the Environment `.json` files;
2. Set your custom entrypoint (i.e. `http://localhost/api/`);
3. You must run at least the POST `Create User`;
4. Get the session token using POST `Get JWT Token`.