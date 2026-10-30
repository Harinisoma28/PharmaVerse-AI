export function extractErrorMessage(error, fallback = "Something went wrong.") {
  const detail = error?.response?.data?.detail;
  const message = error?.response?.data?.message;
  const data = error?.response?.data;

  if (typeof detail === "string" && detail.trim()) return detail;
  if (typeof message === "string" && message.trim()) return message;

  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || item?.loc?.join(".") || JSON.stringify(item))
      .join("; ");
  }

  if (data && typeof data === "object") {
    const entries = Object.entries(data).filter(([, value]) => value != null && value !== "");
    if (entries.length > 0) {
      return entries
        .map(([key, value]) => {
          if (Array.isArray(value)) return `${key}: ${value.join(", ")}`;
          if (typeof value === "object") return `${key}: ${JSON.stringify(value)}`;
          return `${key}: ${value}`;
        })
        .join("; ");
    }
  }

  if (typeof error?.message === "string" && error.message.trim()) return error.message;
  return fallback;
}
