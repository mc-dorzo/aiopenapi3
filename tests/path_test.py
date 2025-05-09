"""
This file tests that paths are parsed and populated correctly
"""

import base64
import copy
import uuid
import pathlib

import pytest
import httpx
import yarl

from aiopenapi3 import OpenAPI
from aiopenapi3.errors import (
    OperationParameterValidationError,
    OperationIdDuplicationError,
    HeadersMissingError,
    HTTPClientError,
    HTTPServerError,
)

URLBASE = "/"


def test_paths_exist(petstore_expanded):
    """
    Tests that paths are parsed correctly
    """
    petstore_expanded_spec = OpenAPI(URLBASE, petstore_expanded)

    assert "/pets" in petstore_expanded_spec.paths._paths
    assert "/pets/{id}" in petstore_expanded_spec.paths._paths
    assert len(petstore_expanded_spec.paths._paths) == 2


def test_operations_exist(petstore_expanded):
    """
    Tests that methods are populated as expected in paths
    """

    petstore_expanded_spec = OpenAPI(URLBASE, petstore_expanded)

    pets_path = petstore_expanded_spec.paths["/pets"]
    assert pets_path.get is not None
    assert pets_path.post is not None
    assert pets_path.put is None
    assert pets_path.delete is None

    pets_id_path = petstore_expanded_spec.paths["/pets/{id}"]
    assert pets_id_path.get is not None
    assert pets_id_path.post is None
    assert pets_id_path.put is None
    assert pets_id_path.delete is not None

    for operation in petstore_expanded_spec._:
        continue


def test_operation_populated(openapi_version, petstore_expanded):
    """
    Tests that operations are populated as expected
    """
    petstore_expanded_spec = OpenAPI(URLBASE, petstore_expanded)

    op = petstore_expanded_spec.paths["/pets"].get

    # check description and metadata populated correctly
    assert op.operationId == "findPets"
    assert op.description.startswith("Returns all pets from the system")
    assert op.summary is None

    # check parameters populated correctly
    assert len(op.parameters) == 2

    param1 = op.parameters[0]
    assert param1.name == "tags"
    assert param1.in_ == "query"
    assert param1.description == "tags to filter by"
    assert param1.required == False
    assert param1.style == "form"
    assert param1.schema_ is not None
    assert param1.schema_.type == "array"
    assert param1.schema_.items.type == "string"

    param2 = op.parameters[1]
    assert param2.name == "limit"
    assert param2.in_ == "query"
    assert param2.description == "maximum number of results to return"
    assert param2.required == False
    assert param2.schema_ is not None
    assert param2.schema_.type == "integer"
    assert param2.schema_.format == "int32"

    # check that responses populated correctly
    assert "200" in op.responses
    assert "default" in op.responses
    assert len(op.responses) == 2

    resp1 = op.responses["200"]
    assert resp1.description == "pet response"
    assert len(resp1.content) == 1
    assert "application/json" in resp1.content
    con1 = resp1.content["application/json"]
    assert con1.schema_ is not None
    assert con1.schema_.type == "array"
    # we're not going to test that the ref resolved correctly here - that's a separate test
    assert type(con1.schema_.items._target) == openapi_version.schema

    resp2 = op.responses["default"]
    assert resp2.description == "unexpected error"
    assert len(resp2.content) == 1
    assert "application/json" in resp2.content
    con2 = resp2.content["application/json"]
    assert con2.schema_ is not None
    # again, test ref resolution elsewhere
    assert type(con2.schema_._target) == openapi_version.schema


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
def test_paths_security(httpx_mock, with_paths_security):
    api = OpenAPI(URLBASE, with_paths_security, session_factory=httpx.Client, use_operation_tags=False)
    httpx_mock.add_response(headers={"Content-Type": "application/json"}, json="user")

    auth = str(uuid.uuid4())

    for i in api.paths.values():
        if not i.post or not i.post.security:
            continue
        s = i.post.security[0]
        #        assert type(s.name) == str
        #        assert type(s.types) == list
        break
    else:
        assert False

    with pytest.raises(ValueError, match=r"does not accept security schemes \['xAuth'\]"):
        api.authenticate(xAuth=auth)
        api._.api_v1_auth_login_info(data={}, parameters={})

    # global security
    api.authenticate(None, cookieAuth=auth)
    api._.api_v1_auth_login_info(data={}, parameters={})
    request = httpx_mock.get_requests()[-1]

    # path
    api.authenticate(None, tokenAuth=auth)
    api._.api_v1_auth_login_create(data={}, parameters={})
    request = httpx_mock.get_requests()[-1]
    assert request.headers["Authorization"] == auth

    api.authenticate(None, paramAuth=auth)
    api._.api_v1_auth_login_create(data={}, parameters={})
    request = httpx_mock.get_requests()[-1]
    assert yarl.URL(str(request.url)).query["auth"] == auth

    api.authenticate(None, cookieAuth=auth)
    api._.api_v1_auth_login_create(data={}, parameters={})
    request = httpx_mock.get_requests()[-1]
    assert request.headers["Cookie"] == f"Session={auth}"

    api.authenticate(None, basicAuth=(auth, auth))
    api._.api_v1_auth_login_create(data={}, parameters={})
    request = httpx_mock.get_requests()[-1]
    assert request.headers["Authorization"].split(" ")[1] == base64.b64encode((auth + ":" + auth).encode()).decode()

    try:
        import httpx_auth
    except:
        api.authenticate(None, digestAuth=(auth, auth))
        api._.api_v1_auth_login_create(data={}, parameters={})
        request = httpx_mock.get_requests()[-1]
    # can't test?

    api.authenticate(None, bearerAuth=auth)
    api._.api_v1_auth_login_create(data={}, parameters={})
    request = httpx_mock.get_requests()[-1]
    assert request.headers["Authorization"] == f"Bearer {auth}"

    # null session - via empty Operation Security
    api.authenticate(None)
    r = api._.api_v1_auth_login_null()
    request = httpx_mock.get_requests()[-1]


def test_paths_security_combined(httpx_mock, with_paths_security):
    api = OpenAPI(URLBASE, with_paths_security, session_factory=httpx.Client, use_operation_tags=False)
    httpx_mock.add_response(headers={"Content-Type": "application/json"}, json="user")

    auth = str(uuid.uuid4())

    # combined
    api.authenticate(user="test")
    with pytest.raises(ValueError, match="No security requirement satisfied"):
        r = api._.api_v1_auth_login_combined(data={}, parameters={})

    api.authenticate(**{"user": "theuser", "token": "thetoken"})
    r = api._.api_v1_auth_login_combined(data={}, parameters={})

    api.authenticate(None)
    with pytest.raises(ValueError, match="No security requirement satisfied"):
        r = api._.api_v1_auth_login_combined(data={}, parameters={})


def test_paths_parameters(httpx_mock, with_paths_parameters):
    httpx_mock.add_response(headers={"Content-Type": "application/json"}, json="test")
    api = OpenAPI(URLBASE, with_paths_parameters, session_factory=httpx.Client)

    with pytest.raises(
        ValueError, match=r"Required Parameter \['Cookie', 'Header', 'Path', 'Query'\] missing \(provided \[\]\)"
    ):
        api._.getTest(data={}, parameters={})

    Header = [i**i for i in range(3)]
    api._.getTest(data={}, parameters={"Cookie": "Cookie", "Path": "Path", "Header": Header, "Query": "Query"})
    request = httpx_mock.get_requests()[-1]

    assert request.headers["Header"] == ",".join(map(str, Header))
    assert request.headers["Cookie"] == "Cookie=Cookie"
    assert pathlib.Path(request.url.path).name == "Path"
    assert yarl.URL(str(request.url)).query["Query"] == "Query"

    with pytest.raises(
        ValueError, match=r"Parameter \['Invalid'\] unknown \(accepted \['Cookie', 'Header', 'Path', 'Query'\]\)"
    ):
        api._.getTest(
            data={},
            parameters={"Cookie": "Cookie", "Path": "Path", "Header": Header, "Query": "Query", "Invalid": "yes"},
        )


def test_paths_parameters_invalid(with_paths_parameters_invalid):
    with pytest.raises(OperationParameterValidationError, match=r"Parameter names are invalid: \[\'\', \'Path:\'\]"):
        OpenAPI(URLBASE, with_paths_parameters_invalid, session_factory=httpx.Client)


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
def test_paths_parameters_oneOf(httpx_mock, with_paths_parameters_oneOf):
    api = OpenAPI(URLBASE, with_paths_parameters_oneOf, session_factory=httpx.Client)
    httpx_mock.add_response(headers={"Content-Type": "application/json"}, json="test")
    api._.getTest(parameters={"nullable_array": ["x", "1"]})
    api._.getTest(parameters={"nullable_array": None})
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        api._.getTest(parameters={"nullable_array": "x"})
    with pytest.raises(pydantic.ValidationError):
        api._.getTest(parameters={"nullable_array": 1})
    with pytest.raises(pydantic.ValidationError):
        api._.getTest(parameters={"nullable_array": {"a": "A"}})

    api._.getTest(parameters={"nullable_object": {"a": "A"}})
    api._.getTest(parameters={"nullable_object": None})
    with pytest.raises(pydantic.ValidationError):
        api._.getTest(parameters={"nullable_object": "x"})
    with pytest.raises(pydantic.ValidationError):
        api._.getTest(parameters={"nullable_object": 1})
    with pytest.raises(pydantic.ValidationError):
        api._.getTest(parameters={"nullable_object": ["x"]})


def test_paths_parameter_missing(with_paths_parameter_missing):
    with pytest.raises(OperationParameterValidationError, match="Parameter name not found in parameters: missing"):
        OpenAPI(URLBASE, with_paths_parameter_missing, session_factory=httpx.Client)


def test_paths_parameter_default(httpx_mock, with_paths_parameter_default):
    httpx_mock.add_response(headers={"Content-Type": "application/json"}, json="default")
    api = OpenAPI(URLBASE, with_paths_parameter_default, session_factory=httpx.Client)
    api._.default()
    request = httpx_mock.get_requests()[-1]
    u = yarl.URL(str(request.url))
    assert u.parts[2] == "op"
    assert u.parts[3] == "path"


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
def test_paths_parameter_format(httpx_mock, with_paths_parameter_format):
    httpx_mock.add_response(headers={"Content-Type": "application/json"}, json="test")
    api = OpenAPI(URLBASE, with_paths_parameter_format, session_factory=httpx.Client)

    # using values from
    # https://spec.openapis.org/oas/v3.1.0#style-examples

    parameters = {
        "array": ["blue", "black", "brown"],
        "string": "blue",
        "empty": None,
        "object": {"R": 100, "G": 200, "B": 150},
        "boolean": False,
        "integer": 100,
        "number": 2**78 * 1.1,
    }

    ne = parameters.copy()
    del ne["empty"]
    r = api._.FormQuery(parameters=parameters)
    request = httpx_mock.get_requests()[-1]
    u = yarl.URL(str(request.url))
    assert u.query["string"] == "blue"
    assert u.query["array"] == ",".join(parameters["array"])
    assert u.query["object"] == "R,100,G,200,B,150"
    assert u.query["empty"] == ""

    r = api._.FormExplodeQuery(parameters=parameters)
    request = httpx_mock.get_requests()[-1]
    u = yarl.URL(str(request.url))
    assert u.query["string"] == "blue"
    assert u.query.getall("array") == parameters["array"]
    assert u.query["R"] == "100" and u.query["G"] == "200" and u.query["B"] == "150"

    #    r = api._.LabelPath(parameters=parameters)
    r = api.createRequest("LabelPath")
    r._prepare(None, parameters)
    assert r.req.url == "/label/query/.blue/.blue.black.brown/.R.100.G.200.B.150/./.false/.100/.3.3245460039402305e+23"
    v = r.request(parameters=parameters)
    request = httpx_mock.get_requests()[-1]
    u = yarl.URL(str(request.url))
    assert u.parts[4] == ".blue"
    assert u.parts[5] == ".blue.black.brown"
    assert u.parts[6] == ".R.100.G.200.B.150"
    # assert u.parts[7] == ""  # . is scrubbed as path self

    r = api._.LabelExplodePath(parameters=parameters)
    request = httpx_mock.get_requests()[-1]
    u = yarl.URL(str(request.url))
    assert u.parts[4] == ".blue"
    assert u.parts[5] == ".blue.black.brown"
    assert u.parts[6] == ".R=100.G=200.B=150"
    assert u.parts[7] == ".false"
    assert u.parts[8] == ".100"
    assert u.parts[9] == ".3.3245460039402305e+23"

    r = api._.deepObjectExplodeQuery(parameters={"object": parameters["object"]})
    request = httpx_mock.get_requests()[-1]
    u = yarl.URL(str(request.url))
    assert u.query["object[R]"] == "100" and u.query["object[G]"] == "200" and u.query["object[B]"] == "150"

    # Matrjoschka
    Matrjoschka = api.components.schemas["Matrjoschka"].get_type()
    o = None
    depth = 3
    for i in range(1, depth + 1):
        o = Matrjoschka(size=i, inner=o)

    for data in [o, o.model_dump()]:
        # {"size": 3, "inner": {"size": 2, "inner": {"size": 1, "inner": {}}}}
        r = api._.deepObjectNestedExplodeQuery(parameters={"object": data})
        request = httpx_mock.get_requests()[-1]
        u = yarl.URL(str(request.url))
        expected = dict(
            list(map(lambda x: (f'object{"".join("[inner]" for _ in range(x))}[size]', depth - x), range(depth)))
        )
        # 'object[size]=3&object[inner][size]=2&object[inner][inner][size]=1'
        assert all(u.query[k] == str(v) for k, v in expected.items())

    r = api._.DelimitedQuery(parameters={"pipe": ["a", "b"], "space": ["1", "2"], "object": parameters["object"]})
    request = httpx_mock.get_requests()[-1]
    u = yarl.URL(str(request.url))
    assert u.query["pipe"] == "a|b"
    assert u.query["space"] == "1 2"
    assert u.query["object"] == "R 100 G 200 B 150"

    r = api._.matrixPath(parameters=parameters)
    request = httpx_mock.get_requests()[-1]
    u = yarl.URL(str(request.url))

    assert u.parts[4] == ";string=blue"
    assert u.parts[5] == ";array=blue,black,brown"
    assert u.parts[6] == ";object=R,100,G,200,B,150"
    assert u.parts[7] == ";empty"
    assert u.parts[8] == ";boolean=false"
    assert u.parts[9] == ";integer=100"
    assert u.parts[10] == ";number=3.3245460039402305e+23"

    r = api._.simpleHeader(parameters=ne)
    request = httpx_mock.get_requests()[-1]
    u = yarl.URL(str(request.url))

    assert request.headers.get("string") == "blue"
    assert request.headers.get("array") == "blue,black,brown"
    assert request.headers.get("object") == "R,100,G,200,B,150"
    assert request.headers.get("boolean") == "false"
    assert request.headers.get("integer") == "100"
    assert request.headers.get("number") == "3.3245460039402305e+23"

    r = api._.simpleExplodePath(parameters=ne)
    request = httpx_mock.get_requests()[-1]
    u = yarl.URL(str(request.url))

    assert u.parts[5] == "blue"
    assert u.parts[6] == "blue,black,brown"
    assert u.parts[7] == "R=100,G=200,B=150"
    assert u.parts[8] == "false"
    assert u.parts[9] == "100"
    assert u.parts[10] == "3.3245460039402305e+23"

    return


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
def test_paths_parameter_format_complex(httpx_mock, with_paths_parameter_format_complex):
    httpx_mock.add_response(headers={"Content-Type": "application/json"}, json="test")

    api = OpenAPI(URLBASE, with_paths_parameter_format_complex, session_factory=httpx.Client)
    r = api._.get()
    r = api._.get(parameters={"value": 5})
    assert r


def test_paths_response_header(httpx_mock, with_paths_response_header):
    httpx_mock.add_response(
        headers={"Content-Type": "application/json", "X-required": "1", "X-optional": "1,2,3"}, json="get"
    )

    api = OpenAPI(URLBASE, with_paths_response_header, session_factory=httpx.Client)
    h, b = api._.get(return_headers=True)
    request = httpx_mock.get_requests()[-1]

    assert isinstance(h["X-required"], str)
    o = h["X-optional"]
    assert isinstance(o, list) and len(o) == 3 and isinstance(o[0], str) and o[-1] == "3"

    with pytest.raises(HeadersMissingError) as e:
        httpx_mock.add_response(headers={"Content-Type": "application/json", "X-optional": "1,2,3"}, json="get")
        h, b = api._.get(return_headers=True)
    assert list(e.value.missing.keys()) == ["x-required"]

    httpx_mock.add_response(headers={"Content-Type": "application/json", "X-object": "A,1,B,2,C,3"}, json="types")
    h, b = api._.types(return_headers=True)
    assert h["X-object"].A == 1
    assert h["X-object"].B == "2"
    return


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
def test_paths_response_content_empty(httpx_mock, with_paths_response_content_empty_vXX):
    httpx_mock.add_response(status_code=200)
    api = OpenAPI(URLBASE, with_paths_response_content_empty_vXX, session_factory=httpx.Client)
    h, b = api._.empty(return_headers=True)
    assert b is None and h == {}

    httpx_mock.add_response(status_code=200, headers={"X-required": "1"})
    h, b = api._.headers(return_headers=True)
    assert b is None and h["X-required"] == "1"


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
def test_paths_response_content_type_octet(httpx_mock, with_paths_response_content_type_octet):
    CONTENT = b"\x00\x11"
    httpx_mock.add_response(headers={"Content-Type": "application/octet-stream", "X-required": "1"}, content=CONTENT)
    api = OpenAPI(URLBASE, with_paths_response_content_type_octet, session_factory=httpx.Client)
    headers, data = api._.header(return_headers=True)
    assert isinstance(headers["X-required"], str)
    assert data == CONTENT
    request = httpx_mock.get_requests()[-1]

    data = api._.octet()
    assert data == CONTENT
    request = httpx_mock.get_requests()[-1]


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
def test_paths_tags(httpx_mock, with_paths_tags):
    import copy

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, json="list")
    api = OpenAPI(URLBASE, with_paths_tags, session_factory=httpx.Client, use_operation_tags=True)
    b = api._.users.list()
    r = frozenset(api._)
    assert frozenset(["items.list", "objects.list", "users.list"]) == r

    from aiopenapi3.errors import SpecError

    with pytest.raises(OperationIdDuplicationError, match="list"):
        OpenAPI(URLBASE, with_paths_tags, session_factory=httpx.Client, use_operation_tags=False)

    spec = copy.deepcopy(with_paths_tags)
    for k in {"/user/", "/item/"}:
        spec["paths"][k]["get"]["operationId"] = f"list{k[1:-1]}"

    api = OpenAPI(URLBASE, spec, session_factory=httpx.Client, use_operation_tags=False)
    api._.listuser()
    r = frozenset(api._)
    assert frozenset(["listuser", "listitem"]) == r


def test_paths_response_status_pattern_default(httpx_mock, with_paths_response_status_pattern_default):
    api = OpenAPI("/", with_paths_response_status_pattern_default, session_factory=httpx.Client)
    api.raise_on_http_status = []

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=201, json="created")
    r = api._.test()
    assert r == "created"

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=200, json="good")
    r = api._.test()
    assert r == "good"

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=500, json="bad")
    r = api._.test()
    assert r == "bad"

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=100, json="unknown")
    r = api._.test()
    assert r == "unknown"

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=500, json="notbad")
    from aiopenapi3.errors import ResponseSchemaError

    with pytest.raises(ResponseSchemaError):
        api._.test()


def test_paths_response_error(mocker, httpx_mock, with_paths_response_error_vXX):
    from aiopenapi3 import ResponseSchemaError, ContentTypeError, HTTPStatusError, ResponseDecodingError

    api = OpenAPI("/", with_paths_response_error_vXX, session_factory=httpx.Client)

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=200, json="ok")
    r = api._.test()
    assert r == "ok"

    httpx_mock.add_response(headers={"Content-Type": "text/html"}, status_code=200, json="ok")
    with pytest.raises(ContentTypeError):
        api._.test()

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=201, json="ok")
    with pytest.raises(HTTPStatusError):
        api._.test()

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=200, content="'")
    with pytest.raises(ResponseDecodingError):
        api._.test()

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=200, json="fail")
    with pytest.raises(ResponseSchemaError):
        api._.test()

    httpx_mock.add_response(headers={"Content-Type": "application/json", "X-required": "1"}, status_code=437, json="ok")
    with pytest.raises(HTTPClientError):
        api._.test()

    httpx_mock.add_response(headers={"Content-Type": "application/json", "X-required": "1"}, status_code=537, json="ok")
    with pytest.raises(HTTPServerError):
        api._.test()

    httpx_mock.add_response(headers={"Content-Type": "application/json", "X-required": "1"}, status_code=437, json="ok")
    mocker.patch.object(api, "raise_on_http_status", return_value=[], autospec=True)
    api._.test()


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
def test_paths_request_calling(httpx_mock, with_paths_response_status_pattern_default):
    api = OpenAPI("/", with_paths_response_status_pattern_default, session_factory=httpx.Client)

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=201, json="created")
    r = api._.test()
    assert r == "created"

    req = api.createRequest("test")
    operationId, path, method = req.operation.operationId, req.path, req.method
    r = req()
    assert r == "created"

    req = api.createRequest((path, method))
    r = req.request()
    assert r.data == "created"

    req = api._[operationId]
    r = req()
    assert r == "created"

    req = api._[(path, method)]
    r = req()
    assert r == "created"


def test_paths_servers(httpx_mock, with_paths_servers):
    api = OpenAPI("/", with_paths_servers, session_factory=httpx.Client)
    assert api.url.host == "servers"

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=200, json="'ok'")
    r = api._.servers()
    request = httpx_mock.get_requests()[-1]
    assert request.url.host == "servers"

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=204)
    r = api._.path()
    request = httpx_mock.get_requests()[-1]
    assert request.url.host == "path"

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=200, json="'ok'")
    r = api._.operation()
    request = httpx_mock.get_requests()[-1]
    assert request.url.host == "operation"

    return


@pytest.mark.httpx_mock(can_send_already_matched_responses=True)
def test_paths_server_variables(httpx_mock, with_paths_server_variables):
    api = OpenAPI("http://example/openapi.yaml", with_paths_server_variables, session_factory=httpx.Client)
    assert api.url.host == "default"

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=200, json="'ok'")
    r = api._.servers()
    request = httpx_mock.get_requests()[-1]
    assert request.url.host == "default"

    api._server_variables = {"host": "defined"}
    r = api._.servers()
    request = httpx_mock.get_requests()[-1]
    assert request.url.host == "defined"

    api._server_variables = {"host": "defoned"}
    with pytest.raises(ValueError, match="Server Variable host value defoned not allowed"):
        api._.servers()

    api._server_variables = dict()

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=204)
    r = api._.path()
    request = httpx_mock.get_requests()[-1]
    assert request.url.host == "example" and request.url.path == "/v1/defined"

    httpx_mock.add_response(headers={"Content-Type": "application/json"}, status_code=200, json="'ok'")
    r = api._.operation()
    request = httpx_mock.get_requests()[-1]
    assert request.url.host == "operation" and request.url.path == "/v3/defined"


def test_paths_server_variables_missing(with_paths_server_variables):
    dd = copy.deepcopy(with_paths_server_variables)
    dd["servers"][0]["url"] = "https://{missing}/test"
    with pytest.raises(ValueError, match=r"Missing Server Variables \[\'missing\'\]"):
        OpenAPI("http://example/openapi.yaml", dd, session_factory=httpx.Client)
