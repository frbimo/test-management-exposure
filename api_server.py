# main.py
from __future__ import annotations

from typing import Optional, List, Union, Literal, Any, Dict
from datetime import datetime, time
from enum import Enum
import uuid

from fastapi import FastAPI, Path, status, Body, APIRouter, Query, HTTPException, Response
from pydantic import BaseModel, Field, validator, model_validator, ConfigDict
import uvicorn
# Custom error handling for fastapi Body. This error due to pydantic and fastapi version that checs inoput before json serializing
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from http import HTTPStatus
from fastapi import Request

from modules.test_report import TestReport
from modules.test_result import TestCase, TestGroup
def convert_validation_errors(validation_error: ValidationError | RequestValidationError) -> list[dict[str, Any]]:
    converted_errors = []
    for error in validation_error.errors():
        converted_error = {
            "type": error["type"],
            "loc": loc_to_dot_sep(error["loc"]),
            "msg": error["msg"],
        }
        converted_errors.append(converted_error)
    return converted_errors


def loc_to_dot_sep(loc: tuple[str | int, ...]) -> str:
    path = ""
    for i, x in enumerate(loc):
        if isinstance(x, str):
            if i > 0:
                path += "."
            path += x
        elif isinstance(x, int):
            path += f"[{x}]"
        else:
            raise TypeError("Unexpected type")
    return path


async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = convert_validation_errors(exc)
    return JSONResponse(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(errors)},
    )
# --- End of custom error handling ---

class ClassName(str, Enum):
    Test_REPORT = "TestReport"
    Test = "Test"

# Mock database
test_report_db: Dict[str, TestReport] = {}
# test_spec_db: Dict[str, TestSpecification] = {} # Storage for reports
# test_result_db: Dict[str, TestResults] = {} # Storage for reports

# --- FastAPI App ---
app = FastAPI(
    title="Test NRM ProvMnS API",
    version="1.0.0",
    description="Simple API to demonstrate Test creation via PUT",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1,
        "displayRequestDuration": True,
        "filter": True,
        "operationsSorter": "alpha",
        "showCommonExtensions": True,
        "showExtensions": True,
        "showObjectSchemaExamples": True,
        "tagsSorter": "alpha",
        "tryItOutEnabled": True,
    }
)

router =  APIRouter(prefix="/ProvMnS/v1alpha1/SubNetwork")

RESOURCE_TAG = "Unified Resources (Test/TestReport)"

@router.put(
    "/{id}",
    # response_model=TestRequestBody, # Return the same structure as received
    responses={
        # 200: {"description": "Resource updated successfully"},
        201: {"description": "Resource created successfully"},
        204: {"description": "Resource updated with no changes"}
    },
    summary="Create or Update an Test",
    tags=["Test Management"]
)

async def create_or_replace_Test( # Renamed for clarity (PUT replaces)
    id: str = Path(..., description="The unique identifier of the subnetwork or related entity."),
    body: TestReport = Body(...),
    response: Response = Response(status_code=status.HTTP_201_CREATED)
):
    """
    Handles the creation or complete replacement of an Test resource
    associated with a SubNetwork, identified by the `id` in the request body.

    - **className**: Class of the parent resource (e.g., SubNetwork).
    - **id**: ID of the parent resource (context for the operation).
    - **Request Body**: Contains the full Test definition.

    This endpoint validates the incoming Test structure, stores it in memory
    (overwriting if the Test ID already exists), and returns the stored Test data.
    """
    print(f"Received PUT request for id={id}")
    
    test_meta_id=body.testMetadata.testId
    if test_meta_id is None:
        print(f"Test Metadata ID is None. Cannot proceed.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Test Metadata ID is None.")
        
    if test_meta_id !=id:
        print(f"Test Metadata ID '{test_meta_id}' does not match the provided ID '{id}'.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Test Metadata ID '{test_meta_id}' does not match the provided ID '{id}'.")
    # TestMetadata.configurationParameters
    print(f"Received Test Metadata (ID: {test_meta_id}):")
    if test_report_db.get(test_meta_id) is not None:
        print(f"Test Metadata ID'{test_meta_id}' already exists in memory. Skip it.")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

        Test_to_store = body.Test
        # DEBUG
        # Test_to_store.TestReportReference = Test_id

        # Test_to_store.TestReportReference = str(uuid.uuid4())
        # Test_report_id = Test_to_store.TestReportReference
    
    test_report_db[test_meta_id] = body

    print(f"Test Report '{test_meta_id}' stored/replaced.")
    return Response(status_code=status.HTTP_201_CREATED)

@router.get(
    "/{id}",
    summary="Retrieve a Test",
    tags=["Test Management"],
    responses={
        200: {"description": "Test report retrieved successfully"},
        404: {"description": "Test report not found"},
    },
    response_model=TestReport,  # Ensure the response is validated through the model
    response_model_exclude_none=True  # Exclude fields with None values
)
async def get_test_report(
    id: str = Path(..., description="The unique identifier of the subnetwork or related entity."),
    response: Response = Response(status_code=status.HTTP_200_OK)
):
    """
    Handles retrieval of a Test Report resource.

    - **className**: Class of the parent resource (e.g., TestReport).
    - **id**: ID of the parent resource.
    """
    print(f"Received GET request for  id={id}")

    if id in test_report_db:
        print(f"Test Report '{id}' found in memory.")
        response.status_code = status.HTTP_200_OK
        # Validate the response through the Pydantic model to apply response_model_exclude_none
        return TestReport.model_validate(test_report_db[id])
    else:
        print(f"Test '{id}' not found in memory.")
        # response.status_code = status.HTTP_404_NOT_FOUND
        # return {"message": f"Test '{id}' not found in memory."}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"TestReport with id '{id}' not found.")
    
    
class TestSchema(BaseModel):
    foo: str
    bar: int

    @model_validator(mode='before')
    @classmethod
    def validate_to_json(cls, value: Any) -> Any:
        print(value)
        if isinstance(value, str):
            return cls(**json.loads(value))
        return value

# --- PATCH Endpoint (Modify) ---
@router.patch(
    "/{id}",
    status_code=status.HTTP_200_OK,
    summary="Partially Update Test Report ID",
    tags=[RESOURCE_TAG],
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid className"},
        status.HTTP_404_NOT_FOUND: {"description": "Resource not found"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation Error"},
        status.HTTP_204_NO_CONTENT: {"description": "Resource updated successfully"},
    },
)
async def update_resource(
    id: str = Path(..., description="The unique identifier of the resource."),
    patch_data_dict: dict = Body(..., description="The patch data for the resource."),
    response: Response = Response(status_code=status.HTTP_200_OK),
):
    print(f"Received PATCH request for {id}")
    if id in test_report_db:
        print(f"Test Report '{id}' found in memory.")

        existing_report = test_report_db[id]
        # # Validate the patch data against the structure of items within testResults
        patched_test_results = []
        if isinstance(patch_data_dict.get("testResults"), list):
            print(patch_data_dict["testResults"])

            for item_data in patch_data_dict["testResults"]:
                # Determine if the item is a TestCase or TestGroup and validate accordingly
                if "groupItems" in item_data:
                    print("TestGroup found")
                    validated_item = TestGroup.model_validate(item_data)
                else:
                    print("TestCase found")
                    validated_item = TestCase.model_validate(item_data)
                patched_test_results.append(validated_item)

            # Update the testResults in the existing report
            updated_report = existing_report.model_copy(update={"testResults": patched_test_results})
            test_report_db[id] = updated_report # Update in the database (in-memory here)

        print(f"Test Report '{id}' updated.")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": f"Resource '{id}' updated successfully."},
        )

    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": f"Resource '{id}' not found."},
    )

# --- DELETE Endpoint ---
@router.delete(
    "/{id}", # Path identifies the specific Test
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an Test by ID",
    tags=["Test Management"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Test not found"},
        status.HTTP_204_NO_CONTENT: {"description": "Test deleted successfully"},
    }
)
async def delete_Test(
    id: str = Path(..., description="The unique identifier of the Test to delete.")
):
    """
    Deletes an existing Test resource identified by its ID.
    """
    print(f"Received DELETE request for Test_id={id}")

    # # --- Check and delete Test ---
    if id not in test_report_db:
        print(f"Test '{id}' not found for DELETE.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test with id '{id}' not found."
        )


    del test_report_db[id]
    print(f"Test Report '{id}' deleted from memory.")

    # Test_report_id = Test_db[id].TestReportReference
    # del Test_report_db[Test_report_id]  # Delete the associated report
    # print(f"Test Report '{Test_report_id}' deleted from memory.")
    
    # del Test_db[id]
    # print(f"Test '{id}' deleted from memory.")

    # # Return No Content response explicitly for clarity
    return Response(status_code=status.HTTP_204_NO_CONTENT)

app.include_router(router)
# app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
# # --- Update Forward References ---
# # Crucial step: Call rebuild for models that might use forward refs directly
# # or indirectly, especially those used in route signatures or complex nesting.
# print("Rebuilding Pydantic models...")
# VsDataContainerItem.model_rebuild()
# TestSingleRequest.model_rebuild()
# TestReportSingle.model_rebuild()
# TestPatchRequest.model_rebuild()
# TestReportPatchRequest.model_rebuild()
# # Add others if necessary, but these cover the main request/response types
# # and the known forward reference.
# print("Pydantic models rebuilt.")
# --- Run the server ---
if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)