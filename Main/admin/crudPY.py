from flask import Blueprint

crud = Blueprint('crud', __name__)

# CRUD operations can be defined here if we want to decouple from adminPY.
# For simplicity, they are partially implemented in adminPY and teacherPY.