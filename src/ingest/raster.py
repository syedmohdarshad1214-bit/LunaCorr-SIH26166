"""Bounded reads of inspected, uncompressed PDS4 image/spectral arrays.

No archive extraction or whole-cube loading. Unsupported layouts fail explicitly.
"""

from dataclasses import dataclass
import math
from pathlib import Path

from defusedxml import ElementTree as ET
import numpy as np

from src.geometry.footprints import PDS, _one_text


DTYPES = {'UnsignedByte':'u1', 'SignedByte':'i1',
          'UnsignedLSB2':'<u2', 'UnsignedMSB2':'>u2',
          'SignedLSB2':'<i2', 'SignedMSB2':'>i2',
          'UnsignedLSB4':'<u4', 'UnsignedMSB4':'>u4',
          'SignedLSB4':'<i4', 'SignedMSB4':'>i4',
          'IEEE754LSBSingle':'<f4', 'IEEE754MSBSingle':'>f4',
          'IEEE754LSBDouble':'<f8', 'IEEE754MSBDouble':'>f8'}


@dataclass
class RasterLayout:
    product_lid: str
    file_name: str
    shape: tuple
    axes: tuple
    dtype: str
    offset: int
    scaling: float
    value_offset: float
    special_constants: tuple


def inspect_layout(label_path):
    path = Path(label_path)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('PDS4 label exceeds 16 MiB limit')
    root = ET.parse(path).getroot()
    if root.tag != f'{{{PDS}}}Product_Observational':
        raise ValueError('Expected PDS4 Product_Observational')
    lid = _one_text(root, f'{{{PDS}}}Identification_Area/{{{PDS}}}logical_identifier')
    choices = []
    for area in root.findall(f'{{{PDS}}}File_Area_Observational'):
        for array in area:
            if array.tag in {f'{{{PDS}}}{name}' for name in ('Array_2D_Image','Array_3D_Image','Array_3D_Spectrum')}:
                choices.append((area,array))
    if len(choices) != 1:
        raise ValueError('Reader requires exactly one supported observational image/spectral array')
    area,array = choices[0]
    file_name = _one_text(area, f'{{{PDS}}}File/{{{PDS}}}file_name')
    if Path(file_name).name != file_name or '\\' in file_name:
        raise ValueError('Unsupported embedded file path')
    if _one_text(array, f'{{{PDS}}}axis_index_order') != 'Last Index Fastest':
        raise ValueError('Unsupported axis storage order')
    axes = []
    for axis in array.findall(f'{{{PDS}}}Axis_Array'):
        axes.append((int(_one_text(axis,f'{{{PDS}}}sequence_number')),
                     _one_text(axis,f'{{{PDS}}}axis_name'),
                     int(_one_text(axis,f'{{{PDS}}}elements'))))
    axes.sort()
    ndim = int(_one_text(array,f'{{{PDS}}}axes'))
    if len(axes) != ndim or ndim not in (2,3) or [a[0] for a in axes] != list(range(1,ndim+1)):
        raise ValueError('Invalid axis dimensions/sequences')
    names = tuple(a[1] for a in axes)
    if set(names) != ({'Line','Sample'} if ndim == 2 else {'Line','Sample','Band'}):
        raise ValueError(f'Unsupported axis names: {names}; inspect product before adding an adapter')
    shape = tuple(a[2] for a in axes)
    if any(n <= 0 for n in shape):
        raise ValueError('Nonpositive array dimension')
    datatype = _one_text(array,f'{{{PDS}}}Element_Array/{{{PDS}}}data_type')
    if datatype not in DTYPES:
        raise ValueError(f'Unsupported PDS4 data_type: {datatype}')
    offsets=array.findall(f'{{{PDS}}}offset')
    if len(offsets)!=1 or offsets[0].get('unit')!='byte':
        raise ValueError('One byte-valued array offset is required')
    offset=int(offsets[0].text)
    if offset<0:
        raise ValueError('Negative array offset')
    def optional_number(name, default):
        nodes=array.findall(f'{{{PDS}}}Element_Array/{{{PDS}}}{name}')
        if len(nodes)>1:
            raise ValueError(f'Ambiguous {name}')
        value=float(nodes[0].text) if nodes else default
        if not math.isfinite(value):
            raise ValueError(f'Nonfinite {name}')
        return value
    constants=[]
    for special in array.findall(f'{{{PDS}}}Special_Constants'):
        for item in special:
            name=item.tag.rsplit('}',1)[-1]
            if name.endswith('_constant'):
                constants.append(float(item.text))
    return RasterLayout(lid,file_name,shape,names,DTYPES[datatype],offset,
                        optional_number('scaling_factor',1),optional_number('value_offset',0),tuple(constants))


def read_window(label_path, science_path, window, bands=None, max_output_bytes=64*1024*1024):
    """Return selected [band,line,sample] float32 data and per-sample validity.

    window = [row_start, col_start, height, width]; band indexes are zero-based.
    Band selection precedes materialization; returned memory is bounded by config.
    """
    layout=inspect_layout(label_path)
    science_path=Path(science_path)
    if science_path.name != layout.file_name:
        raise ValueError('Science filename does not match the PDS4 label')
    if len(window)!=4 or any(type(v) is not int for v in window):
        raise ValueError('Window must contain four integers')
    row,col,height,width=window
    if min(row,col)<0 or min(height,width)<=0:
        raise ValueError('Invalid read window')
    if row+height>layout.shape[layout.axes.index('Line')] or col+width>layout.shape[layout.axes.index('Sample')]:
        raise ValueError('Read window extends outside the source array')
    if 'Band' in layout.axes:
        count=layout.shape[layout.axes.index('Band')]
        if bands is None or not bands:
            raise ValueError('Spectral data requires an explicit, screened band subset')
        if len(bands)>=count:
            raise ValueError('Whole-cube band selection is disabled; choose a screened subset')
        if len(set(bands))!=len(bands) or any(type(b) is not int or not 0<=b<count for b in bands):
            raise ValueError('Invalid or duplicate zero-based band index')
    else:
        if bands not in (None,[0]):
            raise ValueError('A 2D image has only band index 0')
        bands=[0]
    # Includes the returned float data and validity; transient buffers stay band-sized.
    output_bytes=len(bands)*height*width*5
    if output_bytes>max_output_bytes:
        raise ValueError(f'Window exceeds output memory budget ({output_bytes} bytes)')
    expected=layout.offset+math.prod(layout.shape)*np.dtype(layout.dtype).itemsize
    if science_path.stat().st_size<expected:
        raise ValueError('Truncated science file for declared array layout')
    mapped=np.memmap(science_path,mode='r',dtype=layout.dtype,offset=layout.offset,shape=layout.shape,order='C')
    output=np.empty((len(bands),height,width),dtype=np.float32)
    validity=np.empty(output.shape,dtype=bool)
    for k,band in enumerate(bands):
        selection=tuple(slice(row,row+height) if a=='Line' else slice(col,col+width) if a=='Sample' else band for a in layout.axes)
        block=mapped[selection]
        remaining=[a for a in layout.axes if a!='Band']
        if remaining==['Sample','Line']:
            block=block.T
        valid=np.isfinite(block)
        for value in layout.special_constants:
            valid &= block != value
        output[k]=block
        output[k]*=layout.scaling
        output[k]+=layout.value_offset
        valid &= np.isfinite(output[k])
        output[k][~valid]=np.nan
        validity[k]=valid
    del mapped
    return output,validity,{'product_lid':layout.product_lid,'source_shape':list(layout.shape),
           'source_axes':list(layout.axes),'window':window,'bands_zero_based':bands,
           'reader':'numpy.memmap selected-band spatial slices','output_bytes':output_bytes,
           'whole_cube_materialized':False,'storage_note':'OS page reads may include neighboring interleaved samples.'}
