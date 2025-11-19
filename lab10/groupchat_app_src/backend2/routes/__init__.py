import importlib
import pkgutil
from fastapi import FastAPI

def register_routes(app: FastAPI):

    package_name = __name__
    
    for _, module_name, ispkg in pkgutil.iter_modules(__path__):
        if module_name.endswith("_routes") and not ispkg:
            full_module_name = f"{package_name}.{module_name}"
            module = importlib.import_module(full_module_name)

            router = getattr(module, "router", None)
            if router is not None:
                app.include_router(router)
                print(f"Registered router: {module_name}")
            else:
                print(f"Skipped {module_name} (no 'router' variable)")