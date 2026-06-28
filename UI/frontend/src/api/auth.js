import request from "./request";

export function login(username, password) {
  return request.post("/auth/login", { username, password });
}

export function register(username, email, password) {
  return request.post("/auth/register", { username, email, password });
}
