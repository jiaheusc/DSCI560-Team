from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

# auth
class TokenData(BaseModel):
    username: str
    role: str
    user_id: int

class AuthPayload(BaseModel):
    username: str
    password: str

class ChangePasswordPayload(BaseModel):
    old_password: str
    new_password: str

# user
class UserProfileCreate(BaseModel):
    avatar_url: Optional[str] = None
    prefer_name: Optional[str] = None
    bio: Optional[str] = None

class UserProfileUpdate(UserProfileCreate):
    pass

class UserPublicDetail(BaseModel):
    user_id: int
    username: str
    avatar_url: Optional[str] = None
    prefer_name: Optional[str] = None
    bio: Optional[str] = None

    class Config:
        from_attributes = True

class UserPrivateDetail(BaseModel):
    user_id: int
    avatar_url: Optional[str] = None
    prefer_name: Optional[str] = None
    bio: Optional[str] = None
    ai_summary: Optional[str] = None
    mood_state: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    class Config:
        from_attributes = True

class AssignTherapistPayload(BaseModel):
    therapist_id: int

class UserProfileWrappedResponse(BaseModel):
    ok: bool = True
    profile: UserPublicDetail

# Therapist 
class TherapistProfileCreate(BaseModel):
    avatar_url: Optional[str] = None
    prefer_name: Optional[str] = None
    bio: Optional[str] = None
    expertise: Optional[str] = None
    years_experience: Optional[int] = None
    license_number: Optional[str] = None

class TherapistProfileUpdate(TherapistProfileCreate):
    pass

class TherapistPublicDetail(BaseModel):
    user_id: int
    avatar_url: Optional[str] = None
    prefer_name: Optional[str] = None
    bio: Optional[str] = None
    expertise: Optional[str] = None
    years_experience: Optional[int] = None
    
    class Config:
        from_attributes = True

class TherapistPrivateDetail(BaseModel):
    user_id: int
    username: str
    avatar_url: Optional[str] = None
    prefer_name: Optional[str] = None
    bio: Optional[str] = None
    expertise: Optional[str] = None
    years_experience: Optional[int] = None
    license_number: Optional[str] = None

    class Config:
        from_attributes = True

class UserTherapistRelationship(BaseModel):
    has_therapist: bool
    therapist: Optional[TherapistPublicDetail] = None

class TherapistListResponse(BaseModel):
    therapists: List[TherapistPublicDetail]

class TherapistProfileWrappedResponse(BaseModel):
    ok: bool = True
    profile: TherapistPrivateDetail

class PatientSummaryForTherapist(BaseModel):
    id: int
    username: str
    prefer_name: Optional[str] = None
    avatar_url: Optional[str] = None
    unread: int
    
    class Config:
        from_attributes = True

class PatientListResponse(BaseModel):
    users: List[PatientSummaryForTherapist]



# user <-> therapist chat
class ChatSendPayload(BaseModel):
    target_id: int
    message: str

class MarkReadPayload(BaseModel):
    message_id: int

class ChatMessageResponse(BaseModel):
    id: int
    sender_id: int
    message: str
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatMessageListResponse(BaseModel):
    messages: List[ChatMessageResponse]


# group chat
class MessagePayload(BaseModel):
    content: str
    group_id: int

class GroupMessageResponse(BaseModel):
    id: int
    username: str
    content: str
    is_bot: bool
    created_at: datetime 
    
    class Config:
        from_attributes = True

class GroupMessageListResponse(BaseModel):
    messages: List[GroupMessageResponse]

class ChatGroupCreate(BaseModel):
    group_name: Optional[str] = "new group"
    usernames: List[str]

class ChatGroupResponse(BaseModel):
    id: int
    group_name: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True

class ChatGroupListResponse(BaseModel):
    groups: List[ChatGroupResponse]


class ChatGroupUpdate(BaseModel):
    group_name: str

class MemberAdd(BaseModel):
    username: str

# mailbox
class MailMarkReadPayload(BaseModel):
    mail_id: int

class MailApprovePayload(BaseModel):
    user_id: int

class MailSendPayload(BaseModel):
    target_id: int
    message: str

class MailSendSuccessResponse(BaseModel):
    ok: bool = True
    mail_id: int

class MailboxMessageResponse(BaseModel):
    id: int
    from_user: Optional[int]
    to_user: int
    content: dict
    is_read: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class MailboxListResponse(BaseModel):
    messages: List[MailboxMessageResponse]

# questionnaire
class QuestionnairePayload(BaseModel):
    content: dict