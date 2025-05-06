import os
import re
import time
import requests
import pytest
import json
import zipfile

def load_config():
    with open('config.json') as config_file:
        return json.load(config_file)

@pytest.fixture(scope="module")
def setup_files():
    config = load_config()
    file_paths = config['test_files']
    created_files = []

    for file_name in file_paths:
        file_path = file_name
        with open(file_path, 'w') as f:
            f.write(f'Это тестовый файл: {file_name}.')
        created_files.append(file_path)

    yield created_files

    for file_path in created_files:
        if os.path.exists(file_path):
            os.remove(file_path)

@pytest.fixture(scope="module")
def zip_file(setup_files):
    config = load_config()
    file_paths = setup_files
    url = config['upload_url']
    expected_extension = config['expected_extension']

    with requests.Session() as session:
        files = [('files[]', open(file_path, 'rb')) for file_path in file_paths]

        response = session.post(url, files=files)
        assert response.status_code == 200, "Запрос на сервер не отправлен"

        file_names = re.findall(r'filename="([^"]+)"', response.request.body.decode('windows-1251'))

        paths_false = []
        for file_path in file_names:
            actual_extension = os.path.splitext(file_path)[1]
            if actual_extension != expected_extension:
                paths_false.append(file_path)
        if paths_false:
            assert False, f"Файл/ы с именем/ами {paths_false} имеет/ют расширение {actual_extension}, ожидаемое: {expected_extension}"


        zip_file_path = os.path.join(config['zip_file_directory'], time.strftime('%Y%m%d-%H%M%S') + '.zip')
        with zipfile.ZipFile(zip_file_path, 'w') as zip_file:
            for file_path in file_paths:
                zip_file.write(file_path, arcname=os.path.basename(file_path))

        assert os.path.exists(zip_file_path), "Архив не создался"

        for _, file in files:
            file.close()

    return zip_file_path


def test_server_request(setup_files):
    print("test_server_request")
    print("Проверка на выполнение запроса и соответсвие расширения файлов")
    print()
    config = load_config()
    file_paths = setup_files
    url = config['upload_url']
    expected_extension = config['expected_extension']

    with requests.Session() as session:

        files = [('files[]', open(file_path, 'rb')) for file_path in file_paths]

        try:
            response = session.post(url, files=files)

            assert response.status_code == 200, "Запрос выполнен не успешно"

            file_names = re.findall(r'filename="([^"]+)"', response.request.body.decode('windows-1251'))\

            paths_false = []
            for file_path in file_names:
                actual_extension = os.path.splitext(file_path)[1]
                if actual_extension != expected_extension:
                    paths_false.append(file_path)
            if paths_false:
                assert False, f"Файл/ы с именем/ами {paths_false} имеет/ют расширение {actual_extension}, ожидаемое: {expected_extension}"

        finally:
            for _, file in files:
                file.close()

@pytest.mark.usefixtures("zip_file")
def test_zip_creation(setup_files):
    print("test_zip_creation")
    print("Проверка на создание архива")
    print()
    config = load_config()
    file_paths = setup_files
    expected_extension = config['expected_extension']

    zip_file_path = os.path.join(config['zip_file_directory'], time.strftime('%Y%m%d-%H%M%S') + '.zip')
    with zipfile.ZipFile(zip_file_path, 'w') as zip_file:
        for file_path in file_paths:
            if file_path.endswith(expected_extension):
                zip_file.write(file_path, arcname=os.path.basename(file_path))

    assert os.path.exists(zip_file_path), "Архив не создался"

@pytest.mark.usefixtures("zip_file")
def test_zip_contents(zip_file):
    print("test_zip_contents")
    print("Проверка что все загруженные файлы находятся в архиве")
    print()
    config = load_config()
    zip_file_path = zip_file
    expected_file_names = config['test_files']

    with zipfile.ZipFile(zip_file_path, 'r') as zip_file:
        zip_contents = zip_file.namelist()

    assert sorted(zip_contents) == sorted(expected_file_names), \
        f"Некоторые файлы отсутствуют: {set(expected_file_names) - set(zip_contents)}"

@pytest.mark.usefixtures("zip_file")
def test_zip_file_sizes(zip_file, setup_files):
    print("test_zip_file_sizes")
    print("Проверка что все файлы в архиве имеют такой же размер как до загрузки")
    print()
    zip_file_path = zip_file
    original_file_sizes = [os.path.getsize(file_path) for file_path in setup_files]
    original_file_names = [os.path.basename(file_path) for file_path in setup_files]

    with zipfile.ZipFile(zip_file_path, 'r') as zip_file:
        zip_file_sizes = [zip_file.getinfo(file_name).file_size for file_name in zip_file.namelist()]
        zip_file_names = zip_file.namelist()

    size_mapping = dict(zip(original_file_names, original_file_sizes))

    discrepancies = []
    for zip_file_name, zip_file_size in zip(zip_file_names, zip_file_sizes):
        original_size = size_mapping.get(zip_file_name)
        if original_size is not None and original_size != zip_file_size:
            discrepancies.append((zip_file_name, original_size, zip_file_size))

    if discrepancies:
        discrepancy_messages = [f"Файл '{name}': оригинальный размер {orig_size} байт, размер в ZIP {zip_size} байт"
                                for name, orig_size, zip_size in discrepancies]
        assert False, "Несоответствие размеров файлов:\n" + "\n".join(discrepancy_messages)

    assert True

@pytest.mark.usefixtures("zip_file")
def test_zip_directory_contents():
    print("test_zip_directory_contents")
    print("Проверка что в директрории с архивами, только архивы")
    print()
    config = load_config()
    zip_dir = config['zip_file_directory']

    files_in_directory = os.listdir(zip_dir)

    for file_name in files_in_directory:
        assert file_name.endswith('.zip'), f'Файл {file_name} не является ZIP-архивом.'

    assert any(file.endswith('.zip') for file in files_in_directory), 'В директории нет ZIP-архивов.'



# @pytest.mark.parametrize("zip_file_name, expected_file_names", [
#     ('20250324-121532.zip', ['MANIFEST.txt']),
# ])
# def test_parametrize_zip_contents(zip_file_name, expected_file_names):
#     config = load_config()
#     zip_file_path = os.path.join(config['zip_file_directory'], zip_file_name)
#
#     with zipfile.ZipFile(zip_file_path, 'r') as zip_file:
#         zip_contents = zip_file.namelist()
#
#     assert sorted(zip_contents) == sorted(expected_file_names), \
#         f"Некоторые файлы отсутствуют: {set(expected_file_names) - set(zip_contents)}"
#
#
# @pytest.mark.parametrize("zip_file_name, expected_file_sizes", [
#     ('20250324-121532.zip', [3020])
# ])
# def test_parametrize_zip_file_sizes(zip_file_name, expected_file_sizes):
#     config = load_config()
#     zip_file_path = os.path.join(config['zip_file_directory'], zip_file_name)
#
#     with zipfile.ZipFile(zip_file_path, 'r') as zip_file:
#         zip_file_sizes = [zip_file.getinfo(file_name).file_size for file_name in zip_file.namelist()]
#         zip_file_names = zip_file.namelist()
#
#     if sorted(zip_file_sizes) != sorted(expected_file_sizes):
#         discrepancies = []
#         for expected_size, actual_size, file_name in zip(expected_file_sizes, zip_file_sizes, zip_file_names):
#             if expected_size != actual_size:
#                 discrepancies.append((file_name, expected_size, actual_size))
#
#         discrepancy_messages = [
#             f"Файл '{name}': ожидаемый размер {expected_size} байт, фактический размер {actual_size} байт"
#             for name, expected_size, actual_size in discrepancies
#         ]
#
#         assert False, "Несоответствие размеров файлов:\n" + "\n".join(discrepancy_messages)
#
#     assert True
#
#
# @pytest.mark.parametrize("zip_file_name, expected_extension", [
#     ('20250324-120628.zip', '.txt')
# ])
# def test_parametrize_zip_contains_only_files_of_type(zip_file_name, expected_extension):
#     config = load_config()
#     expected_extension = expected_extension
#
#     zip_file_path = os.path.join(config['zip_file_directory'], zip_file_name)
#
#     with zipfile.ZipFile(zip_file_path, 'r') as zip_file:
#         zip_contents = zip_file.namelist()
#
#     for file_name in zip_contents:
#         assert file_name.endswith(expected_extension), f'Файл {file_name} не имеет ожидаемого расширения {expected_extension}.'


if __name__ == '__main__':
    pytest.main()
