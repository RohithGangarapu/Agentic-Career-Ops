import logging
from rich.logging import RichHandler

def get_logger(name="career_ops"):
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Use RichHandler for clean, neat, colored terminal output
        rich_handler = RichHandler(
            show_time=True,
            show_level=True,
            show_path=False,
            rich_tracebacks=True,
            markup=True
        )
        
        # Standard formatter, but RichHandler handles the layout
        formatter = logging.Formatter("%(message)s")
        rich_handler.setFormatter(formatter)
        
        logger.addHandler(rich_handler)
        
    return logger

logger = get_logger()
