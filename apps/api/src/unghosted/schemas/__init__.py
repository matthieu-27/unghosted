"""Pydantic wire models. One import point for controllers."""

from unghosted.schemas.consents import (
    CONSENT_KINDS,
    ConsentGrant,
    ConsentKind,
    ConsentList,
    ConsentRead,
)
from unghosted.schemas.documents import (
    DocumentList,
    DocumentRead,
    DocumentUploadForm,
)
from unghosted.schemas.link_analysis import (
    AnalysisWarningModel,
    ExtractedFieldModel,
    LinkAnalysisBody,
    LinkAnalysisResult,
)
from unghosted.schemas.mail import (
    ApprovedLetterRead,
    DraftRead,
    DraftUpdateBody,
    FirstContactDraftBody,
    Language,
    LetterDraftBody,
    MailWarning,
    SendBody,
    SentEmailRead,
    SentMessageList,
    SentMessageRead,
)
from unghosted.schemas.profiles import (
    ProfileContentUpdate,
    ProfileHighlightModel,
    ProfileRead,
    ProfileVersionRead,
)
from unghosted.schemas.projects import (
    DocumentTypeRead,
    ProjectCreate,
    ProjectList,
    ProjectRead,
    ProjectUpdate,
    StrictModel,
)
from unghosted.schemas.tracker import (
    ColumnDefinitionModel,
    OperationsBody,
    OperationsResult,
    SelectOptionModel,
    TrackerDefinitionModel,
    TrackerPayload,
    TrackerRowModel,
)

__all__ = [
    "CONSENT_KINDS",
    "AnalysisWarningModel",
    "ApprovedLetterRead",
    "ColumnDefinitionModel",
    "ConsentGrant",
    "ConsentKind",
    "ConsentList",
    "ConsentRead",
    "DocumentList",
    "DocumentRead",
    "DocumentTypeRead",
    "DocumentUploadForm",
    "DraftRead",
    "DraftUpdateBody",
    "ExtractedFieldModel",
    "FirstContactDraftBody",
    "Language",
    "LetterDraftBody",
    "LinkAnalysisBody",
    "LinkAnalysisResult",
    "MailWarning",
    "OperationsBody",
    "OperationsResult",
    "ProfileContentUpdate",
    "ProfileHighlightModel",
    "ProfileRead",
    "ProfileVersionRead",
    "ProjectCreate",
    "ProjectList",
    "ProjectRead",
    "ProjectUpdate",
    "SelectOptionModel",
    "SendBody",
    "SentEmailRead",
    "SentMessageList",
    "SentMessageRead",
    "StrictModel",
    "TrackerDefinitionModel",
    "TrackerPayload",
    "TrackerRowModel",
]
