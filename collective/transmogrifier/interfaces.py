import zope.interface

class ITransmogrifier(zope.interface.Interface):
    """The transmogrifier transforms objects through a pipeline"""
    
    portal = zope.interface.Attribute("The targeted Plone portal")
    
    def __call__(self, configuration_id):
        """Load and execute the named pipeline configuration"""
        
    def __getitem__(section):
        """Retrieve a section from the pipeline configuration"""
        
    def keys():
        """List all sections in the pipeline configuration"""
        
    def __iter__():
        """Iterate over all the section names in the pipeline configuration"""


class ISectionBlueprint(zope.interface.Interface):
    """Blueprints create pipe sections"""
    
    def __call__(transmogrifier, name, options, previous):
        """Create a named pipe section for a transmogrifier
        
        Returns an ISection with the given name and options, which will
        use previous as an input iterator when iterated over itself.
        
        """

class ISection(zope.interface.Interface):
    """A section in a transmogrifier pipe"""
    
    def __iter__():
        """Pipe sections are iterables.
        
        During iteration they process the previous section to produce output
        for the next pipe section.
        
        """