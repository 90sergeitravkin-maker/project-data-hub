# src/back/app_kafka/schemas.py
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class BaseSchema(BaseModel):
    model_config = {"from_attributes": True, "extra": "ignore"}


class PartitionInfo(BaseSchema):
    partition: int
    leader: Optional[int] = None
    replicas: List[int] = []
    isr: List[int] = []


class TopicInfo(BaseSchema):
    name: str
    partitions: List[PartitionInfo] = []
    configs: Dict[str, str] = {}
    description: Optional[str] = Field(None, description="Описание топика (из конфигурации)")


class GroupMember(BaseSchema):
    member_id: str
    client_id: str
    host: str


class GroupInfo(BaseSchema):
    group_id: str
    protocol_type: str
    state: str
    members: List[GroupMember] = []


class LagInfo(BaseSchema):
    topic: str
    partition: int
    current_offset: Optional[int] = None
    end_offset: Optional[int] = None
    lag: Optional[int] = None


class GroupDetailResponse(BaseSchema):
    group_id: str
    state: str
    protocol_type: str
    members: List[GroupMember]
    lags: List[LagInfo] = []


class ProduceRequest(BaseSchema):
    topic: str = Field(..., min_length=1, description="Имя топика")
    value: Any = Field(..., description="Сообщение (JSON-сериализуемое)")
    key: Optional[str] = Field(None, description="Ключ сообщения (опционально)")
    partition: Optional[int] = Field(None, description="Номер партиции (опционально)")


class ProduceResponse(BaseSchema):
    status: str = "ok"
    topic: str
    partition: int
    offset: int
    message: str = "Сообщение отправлено"