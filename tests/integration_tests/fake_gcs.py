import os


class FakeBlob:
    def __init__(self, name: str, bucket_path: str) -> None:
        self.name = name
        self.bucket_path = bucket_path
        self._filepath = os.path.join(bucket_path, name)

    def exists(self) -> bool:
        return os.path.exists(self._filepath)

    def download_as_text(self) -> str:
        with open(self._filepath, encoding="utf-8") as f:
            return f.read()

    def download_as_bytes(self) -> bytes:
        with open(self._filepath, "rb") as f:
            return f.read()

    def upload_from_string(
        self, data: bytes | str, content_type: str | None = None
    ) -> None:
        os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
        if isinstance(data, bytes):
            with open(self._filepath, "wb") as f:
                f.write(data)
        else:
            with open(self._filepath, "w", encoding="utf-8") as f:
                f.write(data)


class FakeBucket:
    def __init__(self, name: str, local_root: str) -> None:
        self.name = name
        self.local_root = local_root
        # Each bucket gets its own directory under the local mock root
        self._bucket_path = os.path.join(local_root, name)
        os.makedirs(self._bucket_path, exist_ok=True)

    def exists(self) -> bool:
        return True

    def blob(self, name: str) -> FakeBlob:
        return FakeBlob(name, self._bucket_path)


class FakeStorageClient:
    def __init__(self, local_root: str, project: str | None = None) -> None:
        """
        :param local_root: The root directory where bucket directories will be created.
        """
        self.local_root = local_root
        self.project = project

    def bucket(self, name: str) -> FakeBucket:
        return FakeBucket(name, self.local_root)
