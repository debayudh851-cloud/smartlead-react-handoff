"""Generate a secret-free Postman collection from the current OpenAPI schema."""
import json
from pathlib import Path
import re
import yaml

root = Path(__file__).resolve().parent.parent
schema = yaml.safe_load((root/'docs/openapi.yaml').read_text(encoding='utf-8'))
components = schema['components']['schemas']


def example(node, name='', depth=0):
    if depth > 8:
        return None
    if '$ref' in node:
        return example(components[node['$ref'].split('/')[-1]], name, depth+1)
    if 'allOf' in node:
        return example(node['allOf'][0], name, depth+1)
    if name in {'password','current_password','new_password','confirm_password'}:
        return '{{'+name+'}}'
    if name in {'refresh','uid','token','username','email'}:
        return '{{'+name+'}}'
    if 'enum' in node:
        return next((value for value in node['enum'] if value is not None), None)
    if node.get('type') == 'object':
        return {key:example(value,key,depth+1) for key,value in node.get('properties',{}).items() if not value.get('readOnly') and (key in node.get('required',[]) or key in {'status','assigned_to','is_read','is_approved'})}
    if node.get('type') == 'array':
        return []
    if node.get('type') in {'integer','number'}:
        return max(node.get('minimum',1),1)
    if node.get('type') == 'boolean':
        return True
    if node.get('format') == 'date-time':
        return '{{follow_up_date}}'
    if node.get('format') == 'email':
        return '{{email}}'
    if name in {'budget','price','starting_price'}:
        return '50000.00'
    if name == 'traffic_source':
        return 'Google'
    return 'example'


folders = {}
for path, operations in schema['paths'].items():
    if path in {'/api/schema/', '/api/docs/'}:
        continue
    for method, operation in operations.items():
        if method not in {'get','post','put','patch','delete'}:
            continue
        route = re.sub(r'\{([^}]+)\}', lambda match: '{{'+match.group(1)+'}}', path)
        headers=[]
        request={'method':method.upper(), 'header':headers, 'url':'{{base_url}}'+route, 'description':operation.get('description','')+'\nSee docs/API_CONTRACT.md for roles, filters and error expectations.'}
        request['auth']={'type':'bearer','bearer':[{'key':'token','value':'{{access}}','type':'string'}]} if operation.get('security') and all(rule for rule in operation['security']) else {'type':'noauth'}
        content=operation.get('requestBody',{}).get('content',{})
        if 'application/json' in content:
            body=example(content['application/json']['schema'])
            request['body']={'mode':'raw','raw':json.dumps(body,indent=2),'options':{'raw':{'language':'json'}}}
            headers.append({'key':'Content-Type','value':'application/json'})
        elif 'multipart/form-data' in content:
            request['body']={'mode':'formdata','formdata':[{'key':'service','value':'{{service_id}}','type':'text'},{'key':'alt_text','value':'Service illustration','type':'text'},{'key':'image','type':'file','src':[]}]}
        if path == '/api/enquiries/' and method == 'post':
            headers.append({'key':'Idempotency-Key','value':'{{idempotency_key}}'})
        item={'name':method.upper()+' '+path,'request':request,'response':[]}
        item['event']=[{'listen':'test','script':{'type':'text/javascript','exec':['pm.test("Response is not a server error", function () { pm.expect(pm.response.code).to.be.below(500); });']}}]
        if method=='post' and path in {'/api/auth/login/','/api/token/','/api/user/login/','/api/admin/login/','/api/superuser/login/'}:
            item['event'][0]['script']['exec'] += ['if (pm.response.code === 200) { const data = pm.response.json(); pm.environment.set("access", data.access); pm.environment.set("refresh", data.refresh); }']
        group=path.removeprefix('/api/').split('/')[0]
        folders.setdefault(group,[]).append(item)
collection={'info':{'name':'SMARTLEAD Current API','schema':'https://schema.getpostman.com/json/collection/v2.1.0/collection.json','description':'Generated from current OpenAPI. Set environment values and choose the correct user/staff/super-admin token. Examples require fixture IDs; they are not recorded execution results.'},'item':[{'name':name,'item':items} for name,items in folders.items()]}
values={'base_url':'http://127.0.0.1:8000','username':'replace-with-your-user','email':'user@example.com','password':'','current_password':'','new_password':'','confirm_password':'','access':'','refresh':'','uid':'','token':'','id':'1','service_id':'1','lead_id':'1','follow_up_date':'2030-01-01T12:00:00Z','idempotency_key':'replace-with-unique-request-key'}
environment={'name':'SMARTLEAD Local Template','values':[{'key':key,'value':value,'enabled':True} for key,value in values.items()], '_postman_variable_scope':'environment'}
out=root/'postman'
out.mkdir(exist_ok=True)
(out/'SMARTLEAD.postman_collection.json').write_text(json.dumps(collection,indent=2),encoding='utf-8')
(out/'SMARTLEAD.postman_environment.json').write_text(json.dumps(environment,indent=2),encoding='utf-8')
print(f'Generated {sum(len(items) for items in folders.values())} API requests; no private credentials included.')
