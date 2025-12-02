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

//
// =====================
// Questionnaire
// =====================
export const submitQuestionnaire = (answers, token) =>
  api("/user/questionnaire", "POST", { content: answers }, token);

//
// =====================
// Mailbox
// =====================
export const getMailbox = (token) =>
  api("/mailbox", "GET", null, token);

export const createAutoGroup = (username, token) =>
  api("/chat-groups", "POST", { usernames: [username] }, token);
export const addUserToGroup = (gid, username, token) =>
  api(`/chat-groups/${gid}/member`, "POST", { username }, token);
export const approveUser = (userId, token) =>
  api("/mailbox/approve", "POST", { user_id: userId }, token);

export const markMailRead = (mailId, token) =>
  api("/mailbox/read", "POST", { mail_id: mailId }, token);

export const sendMail = (payload, token) =>
  api("/mailbox/send", "POST", payload, token);

export const getMailPartner = (token) =>
  api("/mailbox/partner", "GET", null, token);

export const getTherapistUserProfile = (userId, token) =>
  api(`/therapist/user/${userId}`, "GET", null, token);

//
// =====================
// Chat Groups & Messages
// =====================
export const createAIChatGroup = (token) =>
  api("/chat-groups/ai-1on1", "POST", null, token);

export const getChatGroups = (token) =>
  api("/chat-groups", "GET", null, token);

export const getMessages = (groupId, token) =>
  api(`/messages?group_id=${groupId}`, "GET", null, token);

export const sendMessageToGroup = (content, groupId, token) =>
  api("/messages", "POST", { content, group_id: groupId }, token);
export async function getUserGroups(userId, token) {
  const res = await fetch(`/api/therapist/users/${userId}/groups`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.json();
}

//
// =====================
// Therapist Profile (private)
// =====================
export const getMyTherapistProfile = (token) =>
  api("/therapist/profile/me", "GET", null, token);

export const updateTherapistProfile = (payload, token) =>
  api("/therapist/profile/update", "POST", payload, token);

//
// =====================
// User Profile (private)
// =====================
export const getMyUserProfile = (token) =>
  api("/user/profile/me", "GET", null, token);

export const createUserProfile = (payload, token) =>
  api("/user/profile", "POST", payload, token);

export const updateUserProfile = (payload, token) =>
  api("/user/profile/update", "POST", payload, token);

export const getUserProfileStatus = (token) =>
  api("/user/profile/status", "GET", null, token);

//
// Therapist assignment
//
export const assignTherapist = (therapist_id, token) =>
  api("/user/me/assign-therapist", "POST", { therapist_id }, token);

//
// =====================
// Avatars & Password (shared)
// =====================
export const listAvatars = (token) =>
  api("/avatars", "GET", null, token);

export const changePassword = (old_password, new_password, token) =>
  api("/auth/change-password", "POST", { old_password, new_password }, token);

//
// =====================
// Therapist List & Public Profile
// =====================
export const listTherapists = (token) =>
  api("/therapist/therapists", "GET", null, token);

export const getPublicTherapistProfile = (id) =>
  api(`/therapist/profile/${id}`, "GET");
