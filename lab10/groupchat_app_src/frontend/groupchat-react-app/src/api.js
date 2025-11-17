export const api = async (path, method = "GET", body, token) => {
  const res = await fetch(`/api${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: body ? JSON.stringify(body) : undefined
  });

  if (!res.ok) {
  let text = await res.text();
  let err;

  try {
    err = JSON.parse(text);
  } catch {
    err = { detail: text };
  }

  throw err;
}

  return res.json();
};

// Questionnaire
export const submitQuestionnaire = (answers, token) =>
  api("/user/questionnaire", "POST", { content: answers }, token);

// Mailbox
export const sendMail = (msg, token) =>
  api("/mail/send", "POST", { message: msg }, token);

export const getMailbox = (token) =>
  api("/mailbox", "GET", null, token);

export const approveUser = (userId, token) =>
  api("/mailbox/approve", "POST", { user_id: userId }, token);

export const replyMail = (to_user, message, token) =>
  api("/mail/reply", "POST", { to_user, message }, token);

// Groups & Chat
export const getChatGroups = (token) =>
  api("/chat-groups", "GET", null, token);

export const getMessages = (groupId, token) =>
  api(`/messages?group_id=${groupId}`, "GET", null, token);

export const sendMessageToGroup = (content, groupId, token) =>
  api("/messages", "POST", { content, group_id: groupId }, token);

// Therapist profile
export const getMyProfile = (token) =>
  api("/therapist/profile/me", "GET", null, token);

export const updateProfile = (payload, token) =>
  api("/therapist/profile/update", "POST", payload, token);

// List therapists
export const listTherapists = (token) =>
  api("/therapists", "GET", null, token);
