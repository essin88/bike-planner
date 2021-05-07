
"""
Script to match paths to roads and summarize statistics on road segments 
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterString
from qgis.core import QgsProcessingParameterFeatureSink
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsExpressionContextUtils
import processing
from datetime import datetime

# Settings for script
buffer_size=20
sampling_distance=70
road_segment_lenght=200
field_to_summarize='we'
save_path_ids_to_buffer=True
sample_size='small' # set to 'large' if full sample set is to be used.

#Input data
roads_url=(
        "D:/OneDrive - Trivector AB/Projekt/Cykel mellan tatorter/Spring 2021/Test new alog/data/Roads_test_sample.gpkg|layername=Roads_test_sample"
)

if sample_size=='large':
    paths_url=(
        "D:/OneDrive - Trivector AB/Projekt/Cykel mellan tatorter/Spring 2021/Test new alog/data/Test_sample_bike_paths_all.gpkg|layername=Test_sample_bike_paths_all"
    )
else:
    paths_url=(
        "D:\OneDrive - Trivector AB\Projekt\Cykel mellan tatorter\Spring 2021\Test new alog\data\Test_sample_bike_paths_small.gpkg|layername=Test_sample_bike_paths_small"
    )

def create_dict_from_layer (layer):
    layer_dict={}
    features = layer.getFeatures()
    k=0
    field_names=[]
    for field in layer.fields():
        field_names.append(field.name())
        
    for feature in features:
        k+=1
        f_dict={}
        for name in field_names:
            f_dict={feature[name]}
            if k == 1:
                print(f_dict,name)
                
    

def add_data_to_buffers(buffer_dict,outputs): 
    sum_buffers={}
    create_dict_from_layer(outputs['paths_layer']['OUTPUT'])
    
#    for key,val in buffer_dict.items():
#        sum=0
#        sum_buffers[key]=""
#        #for itms in val: 
#        #    sum+= 
    

    
def load_vlayer(vlayer):
    QgsProject.instance().addMapLayer(vlayer)

def Match (outputs):
    paths=outputs['paths_layer']['OUTPUT'].getFeatures()
    crs = outputs['paths_layer']['OUTPUT'].crs().toWkt()
    buffers_dict= {}
    a=0
    
    for path in paths:
        a+=1
        
        TempLayer = QgsVectorLayer('Linestring?crs='+ crs, 'connector_lines' , 'memory')
        TempLayerDataProvider = TempLayer.dataProvider()
        TempLayerDataProvider.addAttributes([QgsField('PathID', QVariant.String)])
        TempLayer.updateFields()
        TempLayerDataProvider.addFeatures([path])

        alg_params = {
            'DISTANCE': sampling_distance,
            'END_OFFSET': 0,
            'INPUT': TempLayer,
            'START_OFFSET': 0,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['PointsAlongGeometry'] = processing.run('native:pointsalonglines', alg_params)
        
        # Points with index
        alg_params = {
            'INPUT': outputs['PointsAlongGeometry']['OUTPUT']
        }
        outputs['PointsAlongGeometryWithIndex'] = processing.run('native:createspatialindex', alg_params)
        
        # Join attributes by location
        alg_params = {
            'DISCARD_NONMATCHING': True,
            'INPUT': outputs['PointsAlongGeometry']['OUTPUT'],
            'JOIN': outputs['Buffer']['OUTPUT'],
            'JOIN_FIELDS': [''],
            'METHOD': 1,
            'PREDICATE': [0],
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoinAttributesByLocation'] = processing.run('native:joinattributesbylocation', alg_params)
        
        matched_points=outputs['JoinAttributesByLocation']['OUTPUT'].getFeatures()
        
        for point in matched_points:
            
                    
            if point['BuffID'] in buffers_dict:
                buffers_dict[point['BuffID']].add(point['PathID'])
            else:
                buffers_dict[point['BuffID']]=set(point['PathID'])
            
    
    return buffers_dict

def main():
    print (datetime.now() )
    outputs = {}
    paths_layer =QgsVectorLayer(paths_url, "paths", "ogr")
    roads_layer = QgsVectorLayer(roads_url, "roads", "ogr")
    
    alg_params = {
        'INPUT': paths_layer,
        'OPERATION': '',
        'TARGET_CRS': QgsCoordinateReferenceSystem('EPSG:3006'),
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
    outputs['paths_layer'] = processing.run('native:reprojectlayer', alg_params)
    
    #Reprojekt roads to sweref 99
    alg_params = {
        'INPUT': roads_layer,
        'OPERATION': '',
        'TARGET_CRS': QgsCoordinateReferenceSystem('EPSG:3006'),
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
    outputs['roads_layer'] = processing.run('native:reprojectlayer', alg_params)
    
    # Extract layer extent
    alg_params = {
        'INPUT': outputs['paths_layer']['OUTPUT'],
        'ROUND_TO': 0,
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
    outputs['ExtractLayerExtent'] = processing.run('native:polygonfromlayerextent', alg_params)
    
    # Clip roads to extent of paths
    alg_params = {
        'INPUT': outputs['roads_layer']['OUTPUT'],
        'OVERLAY': outputs['ExtractLayerExtent']['OUTPUT'],
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
    outputs['ClipedRoads'] = processing.run('native:clip', alg_params)
    
    # Split lines by maximum length
    alg_params = {
        'INPUT': outputs['ClipedRoads']['OUTPUT'],
        'LENGTH': road_segment_lenght,
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
    outputs['SplitLinesByMaximumLength'] = processing.run('native:splitlinesbylength', alg_params)
    
    # Buffer the road segments
    alg_params = {
            'DISSOLVE': False,
            'DISTANCE': buffer_size,
            'END_CAP_STYLE': 0,
            'INPUT': outputs['SplitLinesByMaximumLength']['OUTPUT'],
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
    outputs['Buffer'] = processing.run('native:buffer', alg_params)
    
    # Buffer with ID
    alg_params = {
        'FIELD_LENGTH': 0,
        'FIELD_NAME': 'BuffID',
        'FIELD_PRECISION': 0,
        'FIELD_TYPE': 0,
        'FORMULA': '$id ','INPUT': outputs['Buffer']['OUTPUT'],
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
    outputs['Buffer'] = processing.run('native:fieldcalculator', alg_params)

    # Create spatial index for buffer layer
    alg_params = {
        'INPUT': outputs['Buffer']['OUTPUT']
        }
    outputs['BufferWithIndex'] = processing.run('native:createspatialindex', alg_params)
    
    # Add IDs to paths
    alg_params = {
            'FIELD_LENGTH': 12,
            'FIELD_NAME': 'PathID',
            'FIELD_PRECISION': 0,
            'FIELD_TYPE': 0,
            'FORMULA': ' $id ',
            'INPUT': outputs['paths_layer']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
    outputs['paths_layer'] = processing.run('native:fieldcalculator', alg_params)
        
    buffers_with_match=Match(outputs)
    add_data_to_buffers(buffers_with_match,outputs)
    print (datetime.now() )
main()