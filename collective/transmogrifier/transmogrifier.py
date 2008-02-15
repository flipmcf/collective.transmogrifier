import re
import ConfigParser
import UserDict

from zope.component import adapts, getUtility

from Products.CMFCore.interfaces import ISiteRoot

from interfaces import ISection
from interfaces import ISectionBlueprint
from interfaces import ITransmogrifier

class ConfigurationRegistry(object):
    def __init__(self):
        self.clear()
    
    def clear(self):
        self._config_info = {}
        self._config_ids = []
    
    def registerConfiguration(self, name, title, description, configuration):
        if name in self._config_info:
            raise KeyError('Duplicate pipeline configuration: %s' % name)
        
        self._config_ids.append(name)
        self._config_info[name] = dict(
            id=name,
            title=title, 
            description=description, 
            configuration=configuration)
            
    def getConfiguration(self, id):
        return self._config_info[id].copy()
        
    def listConfigurationIds(self):
        return tuple(self._config_ids)

configuration_registry = ConfigurationRegistry()


class Transmogrifier(UserDict.DictMixin):
    adapts(ISiteRoot)
    
    def __init__(self, portal):
        self.portal = portal
        
    def __call__(self, configuration_id):
        config_info = configuration_registry.getConfiguration(
            configuration_id)
        parser = ConfigParser.RawConfigParser()
        parser.optionxform = str # case sensitive
        parser.readfp(open(config_info['configuration']))
        
        self._raw = {}
        self._data = {}
        
        for section in parser.sections():
            self._raw[section] = dict(parser.items(section))
            
        options = self._raw['transmogrifier']
        sections = [s.strip() for s in options['pipeline'].split() 
                    if s.strip()]
                
        # Pipeline construction
        pipeline = iter(()) # empty starter section
        for section_id in sections:
            section_options = self[section_id]
            blueprint_id = section_options['blueprint'].decode('ascii')
            blueprint = getUtility(ISectionBlueprint, blueprint_id)
            pipeline = blueprint(self, section_id, section_options, pipeline)
            if not ISection.providedBy(pipeline):
                raise ValueError('Blueprint %s for section %s did not return '
                                 'an ISection' % (blueprint_id, section_id))
            pipeline = iter(pipeline) # ensure you can call .next()
        
        # Pipeline execution
        for item in pipeline:
            pass # discard once processed
        
    def __getitem__(self, section):
        try:
            return self._data[section]
        except KeyError:
            pass
        
        # May raise key error
        data = self._raw[section]
        
        options = Options(self, section, data)
        self._data[section] = options
        options._substitute()
        return options

    def __setitem__(self, key, value):
        raise NotImplementedError('__setitem__')

    def __delitem__(self, key):
        raise NotImplementedError('__delitem__')

    def keys(self):
        return self._raw.keys()

    def __iter__(self):
        return iter(self._raw)

class Options(UserDict.DictMixin):
    def __init__(self, transmogrifier, section, data):
        self.transmogrifier = transmogrifier
        self.section = section
        self._raw = data
        self._cooked = {}
        self._data = {}

    def _substitute(self):
        for key, value in self._raw.items():
            if '${' in value:
                self._cooked[key] = self._sub(value, [(self.section, key)])
        
    def get(self, option, default=None, seen=None):
        try:
            return self._data[option]
        except KeyError:
            pass
        
        value = self._cooked.get(option)
        if value is None:
            value = self._raw.get(option)
            if value is None:
                return default
        
        if '${' in value:
            key = self.section, option
            if seen is None:
                seen = [key]
            elif key in seen:
                raise ValueError('Circular reference in substitutions.')
            else:
                seen.append(key)

            value = self._sub(value, seen)
            seen.pop()

        self._data[option] = value
        return value

    _template_split = re.compile('([$]{[^}]*})').split
    _valid = re.compile('\${[-a-zA-Z0-9 ._]+:[-a-zA-Z0-9 ._]+}$').match
    def _sub(self, template, seen):
        parts = self._template_split(template)
        subs = []
        for ref in parts[1::2]:
            if not self._valid(ref):
                raise ValueError('Not a valid substitution %s.' % ref)
            
            names = tuple(ref[2:-1].split(':'))
            value = self.transmogrifier[names[0]].get(names[1], None, seen)
            if value is None:
                raise KeyError('Referenced option does not exist:', *names)
            subs.append(value)
        subs.append('')

        return ''.join([''.join(v) for v in zip(parts[::2], subs)])
        
    def __getitem__(self, key):
        try:
            return self._data[key]
        except KeyError:
            pass

        v = self.get(key)
        if v is None:
            raise KeyError('Missing option: %s:%s' % (self.section, key))
        return v

    def __setitem__(self, option, value):
        if not isinstance(value, str):
            raise TypeError('Option values must be strings', value)
        self._data[option] = value

    def __delitem__(self, key):
        if key in self._raw:
            del self._raw[key]
            if key in self._data:
                del self._data[key]
            if key in self._cooked:
                del self._cooked[key]
        elif key in self._data:
            del self._data[key]
        else:
            raise KeyError, key

    def keys(self):
        raw = self._raw
        return list(self._raw) + [k for k in self._data if k not in raw]

    def copy(self):
        result = self._raw.copy()
        result.update(self._cooked)
        result.update(self._data)
        return result

    