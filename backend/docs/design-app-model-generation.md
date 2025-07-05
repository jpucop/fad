backend/model/generate.py
--------------------------

 - requirements:
  
  - logging info error warning level only relative to project root
  - exception handling throughout and log short error message and fail-fast
  - isolation of task steps should map one to one to functions more or less
  - all config info constants are declared and loaded on script start 

  - conventions/assumptions the script shall know and leverage:
  
  - all adjacent dirs to model/schema/ dir are assumed org level model definitions as raw json that are expected to match the corresponding schema type is it based on and likewise for nested dirs contained in any dir adjacent to schema/ as stated are assumed to be named the group name under the org
  E.G.: ucop/finapps present and for now that is the only model defs we have 
  
  - app_{name}.json file names are application model definiitions confirmant to the sceham/app.js schema 'type' definitoin.

  - org_{name}.json is model of an org and likewise for group .. so group_finapps.json based on sceaha/grtoup.json ... 

- steps:
  
  - load all schema json files under schema/ sub-dir

  - identify the static schema types from those loaded prior:
    static schema types have a top-level top level `_schema` property with true or false boolean value only when true is it static type 

  - load all model json files 

  - validate loaded models 
   
   - validation checks:
    - all model json files must match to a single schema type by filename convention:
     - `{schematypename}_{modeltypename}.json --> schema/{schematypename}.json`
    - all schema properties must be accounted for in all declared models found and loaded based on that type declared in schema
    - it is ok the there extra properties in the model declarations json files

  - transform model scehama types to json-schema formated objects via genson

   - generate web app scehama type py files via api api call to datamodel_data_generator.generate function
    - output to backend/app/models/

   - generate copy of all model data laoded as well as all static schemas model data as raw json files to backend/app/data/ 



