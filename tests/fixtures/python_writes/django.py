"""Django ORM model-instance regression fixture."""


def update_user(user):
    user.email = "new@example.com"
    user.save()


def delete_order(order):
    order.delete()
