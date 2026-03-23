import os
import helpers.file_converter as file_converter
import re
            
def converter(origin, destination, remove_darker_duplicates=True):
    os.makedirs(destination, exist_ok=True)
    
    for r, d, f in os.walk(origin):
        for file in f:
            name, extension = os.path.splitext(file)
            if not extension:
                full_path = os.path.join(r, file)
                file_converter.heic_to_img(full_path, destination)
            elif extension.lower() in [".pdf"]:
                full_path = os.path.join(r, file)
                file_converter.pdf_to_img(full_path, destination)

    if remove_darker_duplicates:
        file_converter.remove_darker_duplicates(destination)
    
def artifact_cleaner(artifacts_folder, exclude_extensions=[".pdf", ".heic"]):
    # remove PDFs and HEICs from the artifacts folder
    for r, d, f in os.walk(artifacts_folder):
        for file in f:
            name, extension = os.path.splitext(file)
            if extension.lower() in exclude_extensions:
                full_path = os.path.join(r, file)
                os.remove(full_path)
                
def consolidate_file_extensions(artifacts_folder, target_extension=".jpg"):
    for r, d, f in os.walk(artifacts_folder):
        for file in f:
            name, extension = os.path.splitext(file)
            if extension.lower() != target_extension and extension.lower() in [".jpeg", ".jpg"]:
                full_path = os.path.join(r, file)
                new_full_path = os.path.join(r, name + target_extension)
                os.rename(full_path, new_full_path)

def front_back_switch(artifacts_folder, dry_run=False):
    for r, d, f in os.walk(artifacts_folder):
        for file in f:
            name, extension = os.path.splitext(file)
            if extension.lower() in [".jpg", ".jpeg"]:
                if "_1" in name:
                    new_name = name.replace("_1", "-back")
                    if not dry_run:
                        os.rename(os.path.join(r, file), os.path.join(r, new_name + extension))
                    else:
                        print(f"Dry run: Would rename {file} to {new_name + extension}")
                elif "_2" in name:
                    new_name = name.replace("_2", "-front")
                    if not dry_run:
                        os.rename(os.path.join(r, file), os.path.join(r, new_name + extension))
                    else:
                        print(f"Dry run: Would rename {file} to {new_name + extension}")

def front_back_bypattern(artifacts_folder, pattern={"-a": "-front", "-b": "-back"}, dry_run=False):
    for r, d, f in os.walk(artifacts_folder):
        for file in f:
            name, extension = os.path.splitext(file)
            if extension.lower() in [".jpg", ".jpeg"]:
                # check if the pattern match the end of the filename
                for key, value in pattern.items():
                    if name.endswith(key):
                        new_name = name[:-len(key)] + value
                        if not dry_run:
                            os.rename(os.path.join(r, file), os.path.join(r, new_name + extension))
                        else:
                            print(f"Dry run: Would rename {file} to {new_name + extension}")

if __name__ == "__main__":
    front_back_bypattern('artifacts/sitiopostales', dry_run=False)