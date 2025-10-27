from .base import auto_generate_schemas

"""
=====================================================
# Get schemas for a given model
=====================================================
"""


def get_schemas(model):
    """
    Generate schemas for a given model using the auto_generate_schemas function.
    This function returns the create, update, and response schemas for the model.
    :param model: The model class for which schemas are to be generated.
    :return: A tuple containing the create schema, update schema, response schema for all records,
             and response schema for a single record.
    """

    auto_generated_schemas = auto_generate_schemas(model)
    create_schema = auto_generated_schemas[0]
    update_schema = auto_generated_schemas[1]
    response_all_schema = auto_generated_schemas[2]
    response_id_schema = auto_generated_schemas[2]

    return create_schema, update_schema, response_all_schema, response_id_schema