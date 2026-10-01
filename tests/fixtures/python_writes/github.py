"""GitHub API regression fixture."""


def open_issue(repo, title, body):
    repo.create_issue(title=title, body=body)


def merge_pull_request(pr):
    pr.merge()
