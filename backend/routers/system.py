"""System utility endpoints – folder selection, etc."""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/system", tags=["system"])


class SelectFolderResponse(BaseModel):
    success: bool
    folder_path: str | None = None
    message: str | None = None


@router.post("/select-folder", response_model=SelectFolderResponse)
def select_folder():
    """
    Open a native OS folder selection dialog and return the chosen path.

    Uses tkinter.filedialog.askdirectory() – only works in local desktop
    environments where a display is available.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return SelectFolderResponse(
            success=False,
            message="tkinter is not available in this Python environment",
        )

    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        folder_path = filedialog.askdirectory(
            title="选择出差发票文件夹"
        )

        root.destroy()

        if not folder_path:
            return SelectFolderResponse(
                success=False,
                message="用户取消选择文件夹",
            )

        # Normalize path separators for consistency
        folder_path = folder_path.replace("\\", "/")

        return SelectFolderResponse(
            success=True,
            folder_path=folder_path,
        )

    except Exception as e:
        return SelectFolderResponse(
            success=False,
            message=f"打开文件夹选择窗口失败: {str(e)}",
        )