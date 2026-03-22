import os
import helpers.file_converter as file_converter
            
def converter(origin, destination):
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

if __name__ == "__main__":
    pass