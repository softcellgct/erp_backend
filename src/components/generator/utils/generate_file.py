from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from tempfile import NamedTemporaryFile
import pandas as pd

# =====================================================
# Function to generate a CSV file from the provided data
# and return it as a downloadable file response.
# =====================================================


def csv_file_response(data, filename: str):
    df = pd.DataFrame(data)

    with NamedTemporaryFile(
        delete=False, suffix=".csv", mode="w", newline=""
    ) as tmp_file:
        df.to_csv(tmp_file.name, index=False, encoding="utf-8")

    headers = {
        "Content-Disposition": f"attachment; filename={filename}.csv",
        "Content-Type": "text/csv",
    }

    return FileResponse(tmp_file.name, headers=headers, filename=f"{filename}.csv")


# =====================================================
# Function to reorder the columns of a DataFrame based
# =====================================================
def reorder_and_convert_to_dict(result, model):
    df = pd.DataFrame(jsonable_encoder(result))

    model_columns = [column.name for column in model.__table__.columns]
    first_columns = ["id"]
    last_columns = [
        "created_at",
        "updated_at",
        "deleted_at",
        "created_by",
        "updated_by",
        "deleted_by",
    ]
    middle_columns = [
        col for col in model_columns if col not in first_columns + last_columns
    ]
    ordered_columns = first_columns + middle_columns + last_columns

    df = df[ordered_columns]
    data_dict = jsonable_encoder(df.to_dict(orient="records"))

    return data_dict