from model import db, Project, Stories, Entities, Dfd, Dfd_triple, Dfd_triple_group, Requirements, RequirementGroup
# make sure to import all your models correctly
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL
import json, re

from app import app


# define your namespaces
DPV = Namespace('https://w3id.org/dpv#')
DFLOW = Namespace('http://example.com/ontology/dflow#')
UR = Namespace('http://www.example.org/ur#')
TMC = Namespace('http://www.example.org/tmc#')
MSC = Namespace('http://www.example.org/msc#')


def export_from_db():
    # your session to database
    session = db.session

    # list of your models
    models = [Project, Stories, Entities, Dfd, Dfd_triple, Dfd_triple_group, Requirements, RequirementGroup]

    # create a graph
    g = Graph()
    g.bind('dpv', DPV)
    g.bind('dflow', DFLOW)
    g.bind('ur', UR)
    g.bind('tmc', TMC)
    g.bind('msc', MSC)


    with app.app_context():
        # iterate over models and instances and convert all to triples
        for model in models:
            instances = session.query(model).all()  # get all instances
            for instance in instances:
                g.parse(data=instance.to_turtle(), format='turtle')  # add triples to graph

        # serialize the graph to Turtle and save it to a file
        turtle_data = g.serialize(format='turtle')

        with open('export/instances.ttl', 'w') as f:
            f.write(turtle_data)


def export_threat_categories():
    g = Graph()
    
    # Define namespaces
    g.bind('tmc', TMC)
    
    # Threat categories
    code = ["L", "I", "Nr", "D", "DD", "U", "Nc"]
    categories = ["Linkability", "Identifiability", "Non-repudiation", "Detectability", "Disclosure of information", "Unawareness", "Non-compliance"]
    descriptions = [
        "Linkability: The possibility to link the occurrence of different events in a system, which can lead to inferences about user activities or identities.",
        "Identifiability: The ability to uniquely identify a specific individual, typically by aggregating data from different sources, potentially revealing sensitive information about that individual.",
        "Non-repudiation: The inability for a subject (either a data sender or receiver) to deny having performed a particular action, which could lead to accountability issues.",
        "Detectability: The possibility of sensitive activities or data being noticed or discovered in a system, leading to privacy concerns.",
        "Disclosure of information: Unintentional or unauthorized access, use, disclosure, alteration, or destruction of information, often leading to breaches of privacy.",
        "Unawareness: Users may be unaware of data collection, processing, or sharing practices, violating their privacy rights or expectations.",
        "Non-compliance: The system does not comply with legal, regulatory, or policy requirements for data privacy and protection."
    ]

    for i, category in enumerate(categories):
        category_class = URIRef(TMC + code[i])  # create unique URIs
        g.add((category_class, TMC.id, Literal(code[i])))  
        g.add((category_class, RDF.type, TMC.ThreatCategories))  
        g.add((category_class, RDF.type, RDFS.Class))
        g.add((category_class, RDFS.subClassOf, TMC.ThreatTrees))
        g.add((category_class, RDFS.label, Literal(category)))
        g.add((category_class, RDFS.comment, Literal(descriptions[i])))
    
    # Serialize the graph in 'turtle' format
    turtle_data = g.serialize(format='turtle')
    with open('export/threat_categories.ttl', 'w') as f:
        f.write(turtle_data)

def export_threat_trees():
    # Define the Graph
    g = Graph()
    
    # Define namespaces
    g.bind('tmc', TMC)
    
    category_code = ["L", "I", "Nr", "D", "DD", "U", "Nc"]

    # Load JSON data
    with open('threat_trees.json', encoding="utf-8") as file:
        data = json.load(file)

    # Process JSON data
    for threat in data:
        # Create a new node for this threat
        threat_node = URIRef(TMC + threat['threat_code'])
                
        g.add((threat_node, TMC.id, Literal(threat['threat_code'])))

        # Add ThreatTree type to the node
        g.add((threat_node, RDF.type, TMC.ThreatTrees))
        g.add((threat_node, RDF.type, RDFS.Class))

        # Add properties to the node
        g.add((threat_node, TMC.Code, Literal(threat['threat_code'])))
        g.add((threat_node, RDFS.label, Literal(threat['threat_code'])))
        g.add((threat_node, RDFS.comment, Literal(threat['threat_description'])))
            
        # Add the parent node as a superclass of the threat_node
        g.add((threat_node, RDFS.subClassOf, TMC[threat['threat_parent']]))
        
        for example in threat['examples']:
            g.add((threat_node, TMC.Examples, Literal(example)))
        
        if len(threat['criteria']) > 0:
            g.add((threat_node, TMC.Criteria, Literal(threat['criteria'])))
        
        if len(threat['impact']) > 0:
            g.add((threat_node, TMC.Impact, Literal(threat['impact'])))
        
        if len(threat['additional_info']) > 0:
            g.add((threat_node, TMC.Additional_Info, Literal(threat['additional_info'])))
            
        
        if threat['threat_parent'] in category_code:
            category_class = URIRef(TMC + threat['threat_parent'])  # create unique URIs
            g.add((category_class, TMC.hasChildren, threat_node))
        else:
            threat_parent_node = URIRef(TMC + threat['threat_parent'])
            g.add((threat_parent_node, TMC.hasChildren, threat_node))

    # Serialize the graph in RDF/XML format
    turtle_data = g.serialize(format='turtle')
    
    with open('export/threat_trees.ttl', 'w') as f:
        f.write(turtle_data)



def replace_non_alphanumeric(string):
    pattern = r'[^a-zA-Z0-9]'
    return re.sub(pattern, '', string)

def export_design_pattern():
    # Define the Graph
    g = Graph()
    
    g.bind('msc', MSC)

    # Load JSON data
    with open('LTR_resources/patterns.json') as file:
        data = json.load(file)
        
    for pattern in data:
        # Create a new node for this pattern
        pattern_id = replace_non_alphanumeric(pattern['filename'].replace('.md', ''))
        pattern_node = URIRef(MSC + pattern_id)
        
        g.add((pattern_node, MSC.id, Literal(pattern_id)))
        g.add((pattern_node, RDFS.label, Literal(pattern['title'])))
        g.add((pattern_node, RDFS.comment, Literal(pattern['excerpt'])))
        
        # Add the pattern's title
        g.add((pattern_node, MSC.title, Literal(pattern['title'])))
        
        # Add the pattern's type
        g.add((pattern_node, RDF.type, MSC[pattern['type']]))

        # Add the pattern's requirements
        for requirement in pattern['requirements']:
            g.add((pattern_node, MSC.requirement, Literal(requirement)))
        
        # Add the pattern's goal
        if "goal" in pattern:
            g.add((pattern_node, MSC.goal, Literal(pattern['goal'])))
        
        # Add the pattern's excerpt
        g.add((pattern_node, MSC.excerpt, Literal(pattern['excerpt'])))
        
        # Add the pattern's categories
        for category in pattern['categories']:
            g.add((pattern_node, MSC.category, Literal(category)))
        
        # Add the pattern's status
        g.add((pattern_node, MSC.status, Literal(pattern['status'])))

        # Add the pattern's use
        g.add((pattern_node, MSC.use, Literal(pattern['use'])))

        # Add the pattern's com
        g.add((pattern_node, MSC.com, Literal(pattern['com'])))

        # Add the pattern's sim
        g.add((pattern_node, MSC.sim, Literal(pattern['sim'])))

        # Add the pattern's address
        g.add((pattern_node, MSC.address, Literal(pattern['address'])))
        
        # Add other details from heading
        for heading in pattern['heading']:
            g.add((pattern_node, MSC[replace_non_alphanumeric(heading['title'].lower())], Literal(heading['content'])))
            
    # Return the graph
    turtle_data = g.serialize(format='turtle')
    
    with open('export/privacy_design_pattern.ttl', 'w', encoding="utf-8") as f:
        f.write(turtle_data)
        
        
# export_from_db()
export_threat_categories()
export_threat_trees()
# export_design_pattern()