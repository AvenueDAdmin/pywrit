"""Firestore regression fixture."""


def set_document(doc, data):
    doc.set(data)


def delete_document(doc):
    doc.delete()
