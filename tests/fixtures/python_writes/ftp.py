"""ftplib regression fixture."""


def upload_file(ftp, path, data):
    ftp.storbinary(f"STOR {path}", data)
