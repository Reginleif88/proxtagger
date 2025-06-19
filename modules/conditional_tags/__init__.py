"""
Conditional Tags Module for ProxTagger

This module provides automatic tag application based on configurable rules.
"""

from flask import Blueprint

# Create the blueprint
conditional_tags_bp = Blueprint(
    'conditional_tags',
    __name__,
    template_folder='../../templates/conditional_tags',
    static_folder='../../static',
    url_prefix='/conditional-tags'
)

# Import routes to register them with the blueprint
from . import routes