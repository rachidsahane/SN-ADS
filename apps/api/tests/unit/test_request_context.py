import contextvars

from app.infra import request_context as ctx


def test_values_are_empty_outside_a_request() -> None:
    assert ctx.get_request_id() is None
    assert ctx.get_user_id() is None


def test_bound_values_are_visible_until_reset() -> None:
    token = ctx.bind_context(request_id="r-1")
    assert ctx.get_request_id() == "r-1"
    ctx.reset_context(token)
    assert ctx.get_request_id() is None


def test_user_id_set_in_a_copied_context_is_seen_by_the_caller() -> None:
    token = ctx.bind_context(request_id="r-2")
    contextvars.copy_context().run(ctx.set_user_id, "user-1")
    assert ctx.get_user_id() == "user-1"
    ctx.reset_context(token)


def test_set_user_id_without_a_request_is_a_no_op() -> None:
    ctx.set_user_id("user-1")
    assert ctx.get_user_id() is None


def test_route_template_replaces_path_parameters() -> None:
    scope = {"route": object(), "path": "/api/v1/predictions/42", "path_params": {"id": "42"}}
    assert ctx.route_template(scope) == "/api/v1/predictions/{id}"


def test_route_template_is_none_when_no_route_matched() -> None:
    assert ctx.route_template({"path": "/api/whatever", "path_params": {}}) is None
