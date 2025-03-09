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

## Testing

### Some CURL Requests
1. **Create User**: 
```bash
curl -X POST //http:localhost/api/auth/users -H "Content-Type: application/json" -d '{"username" : "demo", "password" : "demopass"}'
```

2. **Login (Get JWT Token)**: 
```bash
curl -X POST //http:localhost/api/auth/users/login -H "Content-Type: application/json" -d '{"username" : "demo", "password" : "demopass"}'
```


### Postman
The application can be tested using the `Postman` configurations present in the respective folder.

Make sure to:
1. Import both the Collection and the Environment `.json` files;
2. Set your custom entrypoint (i.e. `http://localhost/api/`);
3. You must run at least the POST `Create User`;
4. Get the session token using POST `Get JWT Token`.