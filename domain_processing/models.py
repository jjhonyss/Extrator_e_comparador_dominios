from dataclasses import dataclass, field


@dataclass
class FileExtraction:
    filename: str
    domains: set[str] = field(default_factory=set)
    duplicate_count: int = 0
    raw_count: int = 0
    errors: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
