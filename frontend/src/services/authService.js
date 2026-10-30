import api from "./api";

export const getStoredUser = () => {
  try {
    return JSON.parse(localStorage.getItem("user") || "null");
  } catch {
    return null;
  }
};

export const saveAuthSession = (payload = {}) => {
  if (payload.access_token) {
    localStorage.setItem("access_token", payload.access_token);
  }

  if (payload.user) {
    localStorage.setItem("user", JSON.stringify(payload.user));
  }
};

export const login = async (username, password) => {
  const formData = new URLSearchParams();
  formData.append("username", String(username).trim());
  formData.append("password", String(password));

  const response = await api.post("/auth/login", formData, {
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
  });

  saveAuthSession({ access_token: response.data.access_token });
  const user = await getCurrentUser();
  return { ...response.data, user };
};

export const getCurrentUser = async () => {
  const response = await api.get("/auth/me");
  const user = response.data;
  saveAuthSession({ user });
  return user;
};

export const logout = () => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("user");
};
