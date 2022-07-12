from parsers import ParseException, json_parser, yaml_parser
from schema import Schema, SchemaError
from typing import Any
from os import path
import os
import re

LINUX_KEY_VARIABLE_PATTERN = r'\$([a-zA-Z][\w]+|\{[a-zA-Z][\w]+\})$'
DEFAULT_CONFIG_FILES = ('config.json', 'config.yaml', 'config.yml')
ENTITY_NAME_PATTERN = r'^[a-zA-Z][\w]+$'
SUPPORTED_EXTENSIONS = {
    'json': json_parser,
    'yaml': yaml_parser,
    'yml': yaml_parser
}


class ConfigError(Exception):
    pass


class ConfigFileNotFoundError(ConfigError):
    pass


class ConfigValue:

    def __getitem__(self, item):
        return self.__dict__[item]

    def __iter__(self):
        return self.__dict__.keys().__iter__()

    def __len__(self):
        return len(self.__dict__)

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()


class Config:
    __instance = None
    __hold_an_instance = True

    @classmethod
    def hold_an_instance(cls):
        return cls.__hold_an_instance

    @classmethod
    def set_hold_an_instance(cls, value):
        if type(value) is not bool:
            raise ValueError('value must be a bool')
        cls.__hold_an_instance = value

    def __new__(cls, *args, **kwargs):
        raise RuntimeError('A instance of config is not allowed, use Config.get_config() instead')

    @classmethod
    def get_config(cls, schema: dict = None, config_dir: str = 'config', file_name: Any = DEFAULT_CONFIG_FILES):

        if cls.__instance is None:
            instance = cls.__create_new_instance(schema, config_dir, file_name)
            if cls.__hold_an_instance:
                cls.__instance = instance
            else:
                return instance
        return cls.__instance

    @classmethod
    def __create_new_instance(cls, schema, config_dir, file_name):
        file_path = cls.__get_file_path(config_dir, file_name)
        parser = cls.__get_file_parser(file_path)
        file_buff = cls.__get_file_buff(file_path)

        try:
            config = cls.__validate_schema(schema, parser(file_buff))
            return cls.__dict_2_obj(config)
        except SchemaError as e:
            raise ConfigError('Schema validation error', e)

    @classmethod
    def __get_file_parser(cls, file_path):
        try:
            extension = file_path.split('.')[-1]
            return SUPPORTED_EXTENSIONS[extension]
        except KeyError:
            raise ConfigError(f'Supported extensions: {list(SUPPORTED_EXTENSIONS.keys())}')

    @classmethod
    def __get_file_path(cls, config_dir, file_name):
        file_path = f'{os.getcwd()}/{config_dir}/'
        if type(file_name) is str:
            file_name = [file_name]

        for f_name in file_name:
            if path.isfile(file_path + f_name):
                return file_path + f_name

        raise ConfigFileNotFoundError(f'Config file {file_path}{file_name} was not found')

    @classmethod
    def __validate_schema(cls, schema, config_obj):
        if schema is None:
            return config_obj
        elif type(schema) not in (dict, list):
            raise ConfigError('The first config\'s schema element should be a Map or a List')

        return Schema(schema).validate(config_obj)

    @classmethod
    def __get_file_buff(cls, path_file: str):
        with open(path_file, 'r') as f:
            return f.read()

    @classmethod
    def __dict_2_obj(cls, data: Any):
        _type = type(data)

        if _type is dict:
            obj = ConfigValue()
            for key, value in data.items():
                if re.search(ENTITY_NAME_PATTERN, key) is None:
                    raise ConfigError(
                        f'The key {key} is invalid. The entity keys only may have words, number and underscores.')
                setattr(obj, key, cls.__dict_2_obj(value))
            return obj
        if _type in (list, set, tuple):
            return list(map(lambda v: cls.__dict_2_obj(v), data))
        else:
            if type(data) is str and re.search(LINUX_KEY_VARIABLE_PATTERN, data) is not None:
                return cls.interpol_variable(data)
            return data

    @classmethod
    def interpol_variable(cls, data):
        try:
            return os.environ[cls.extract_env_variable_key(data)]
        except KeyError:
            raise ConfigError(f'Environment variable {data} was not found')

    @classmethod
    def extract_env_variable_key(cls, variable):
        variable = variable[1:]
        if variable[0] == '{':
            return variable[1:-1]
        return variable
