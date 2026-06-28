from pathlib import Path

from pydantic import BaseModel, ConfigDict


class Workspace(BaseModel):
    model_config = ConfigDict(frozen=True)

    root_path: Path
    paper_slug: str
