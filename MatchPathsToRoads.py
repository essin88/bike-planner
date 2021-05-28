
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
buffer_size=2 #buffer size in meters for road segment buffer
sampling_distance=65 # point sampling distance for finding matching road segments
road_segment_lenght=150 # Maximum segment lenght for created segments for the road network
field_to_summarize='we' #Field with data to be summarized for road segments
sample_size='small' #set to large' if full sample set is to be used.

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
def delete_fields_from_layer (vlayer):
    fields_to_keep={'fid','PathID',field_to_summarize} #set with field names to keepLayerSet
    fields = vlayer.dataProvider().fields()
    fields_to_delete=[]
    for field in vlayer.fields():
        if field.name() not in fields_to_keep:
            fields_to_delete.append(vlayer.fields().lookupField(field.name()))

    vlayer.dataProvider().deleteAttributes(fields_to_delete)
    vlayer.updateFields()

    return vlayer

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
        field_values=[]
        for name in field_names:
            f_dict[name]=feature[name]

        layer_dict[feature['PathID']]=f_dict


    return layer_dict


def add_data_to_road_segments(buffer_dict,outputs):
    sum_segments={}
    path_id_dict=create_dict_from_layer(outputs['paths_layer']['OUTPUT'])
    road_segments=outputs['RoadSegments']['OUTPUT']
    road_segments_dp=road_segments.dataProvider()
    road_segments_dp.addAttributes([QgsField("Sum",QVariant.Double)])
    road_segments.updateFields()
    road_segments_sum_idx = road_segments.fields().lookupField('Sum')
    aa=0

    for key,val in buffer_dict.items():
        sum=0
        for itms in val:
            sum+= path_id_dict[itms][field_to_summarize]
        sum_segments[key]=sum

    road_segments.startEditing()

    for segment in road_segments.getFeatures():
        if segment ['SegmentID'] in sum_segments:
            road_segments.changeAttributeValue(segment.id(),road_segments_sum_idx,sum_segments[segment ['SegmentID']])



    road_segments.commitChanges()
    load_vlayer(road_segments)


def load_vlayer(vlayer):
    #Just for testing
    QgsProject.instance().addMapLayer(vlayer)

def Match (outputs):
    paths=outputs['paths_layer']['OUTPUT'].getFeatures()
    crs = outputs['paths_layer']['OUTPUT'].crs().toWkt()
    buffers_dict= {}

    for path in paths:

        TempLayer = QgsVectorLayer('Linestring?crs='+ crs, 'paths' , 'memory')
        TempLayerDataProvider = TempLayer.dataProvider()
        TempLayerDataProvider.addAttributes(outputs['paths_layer']['OUTPUT'].fields())
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

        #Checking BufferID and SegmentID for matching points
        for point in matched_points:

            if point['SegmentID'] in buffers_dict:
                buffers_dict[point['SegmentID']].add(point['PathID'])
            else:
                set_to_add=set()
                set_to_add.add(point['PathID'])
                buffers_dict[point['SegmentID']]= set_to_add


    return buffers_dict

def main():

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
    outputs['RoadSegments'] = processing.run('native:splitlinesbylength', alg_params)


    # Road segments with ID
    alg_params = {
        'FIELD_LENGTH': 0,
        'FIELD_NAME': 'SegmentID',
        'FIELD_PRECISION': 0,
        'FIELD_TYPE': 0,
        'FORMULA': '$id ','INPUT': outputs['RoadSegments']['OUTPUT'],
        'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
    outputs['RoadSegments'] = processing.run('native:fieldcalculator', alg_params)

    # Buffer the road segments
    alg_params = {
            'DISSOLVE': False,
            'DISTANCE': buffer_size,
            'END_CAP_STYLE': 0,
            'INPUT': outputs['RoadSegments']['OUTPUT'],
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
    outputs['Buffer'] = processing.run('native:buffer', alg_params)

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

    outputs['paths_layer']['OUTPUT'] = delete_fields_from_layer(outputs['paths_layer']['OUTPUT'])

    buffers_with_match=Match(outputs)
    add_data_to_road_segments(buffers_with_match,outputs)


if __name__ == '__main__':
    main()
