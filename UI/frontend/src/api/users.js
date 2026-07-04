import request from "./request";

export function fetchUsers() {
  return request.get("/users");
}

export function createUser({ username, email, password, role }) {
  return request.post("/users", { username, email, password, role });
}

export function updateUserRole(userId, role) {
  return request.put(`/users/${userId}/role`, { role });
}

export function resetUserPassword(userId, newPassword) {
  return request.put(`/users/${userId}/password`, { new_password: newPassword });
}

export function deleteUser(userId) {
  return request.delete(`/users/${userId}`);
}
