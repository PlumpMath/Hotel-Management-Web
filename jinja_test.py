from jinja2 import Environment, FileSystemLoader
env = Environment(loader = FileSystemLoader('C:/Users/gzc/Desktop/template'))

template = env.get_template('manage_plans.html')

print(template.render({'u':'Andy'}))