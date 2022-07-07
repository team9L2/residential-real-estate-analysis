import pandas as pd
import numpy as np
import re
 
class SalesDataCleaner:
    """ Utility class that cleans real estate sale offers data from a CSV file into a pandas DataFrame for further work on it"""
    
    def __init__(self, url):
        self.url = url
        self.sales_data = None
        self.cleaned = False

    def get_cleaned_data(self):
        return self.sales_data.copy() if self.cleaned else None
    
    def write_to_csv(self, filepath):
        if self.cleaned:
            self.sales_data.to_csv(filepath, index=False)
    
    def clean(self):
        if not self.cleaned:

            self.import_and_format()

            # print(self.sales_data.dtypes)

            self.delete_hyperlink_column()

            self.delete_land_plot_surface_column()

            self.merge_postcodes_localities_columns()

            self.add_region_column()

            self.clean_property_subtype_column()

            self.clean_price_column()

            self.clean_sale_column()

            self.delete_sale_column()

            self.clean_area_column()

            self.clean_area_land_surface_columns()

            self.clean_building_state_column()

            self.remove_duplicate_records()

            self.remove_na_records()

            self.sales_data.rename(columns={"kitchen_has": "equipped_kitchen_has"}, inplace=True)

            self.clean_facades_number_column()

            # self.display()

            #now that the cleaning is done we update the corresponding binary tag
            self.cleaned = True
    

    def import_and_format(self):
        #dtypes are assigned for the columns which won't require additional manipulations
        columns_types = {
            'source':               int,
            'hyperlink':            str,
            'locality':             str,
            'postcode':             str,
            'house_is':             bool,
            'property_subtype':     str,
            'sale':                 str,
            'rooms_number':         float,
            'garden_area':          float,
            'land_surface':         float,
            'facades_number':       float,
            'building_state':       str
        }

        #transformation functions are assigned for columns which will require additional manipulations
        columns_converters = {
            #read_csv has issue with None in Boolean (interpreted as object). I am using "kitchen_has": lambda x: bool(x) if type(x) is bool else Non
            'kitchen_has':          lambda x: SalesDataCleaner.bool_or_keep(x),
            'furnished':            lambda x: SalesDataCleaner.bool_or_keep(x),
            'open_fire':            lambda x: SalesDataCleaner.bool_or_keep(x),
            'terrace':              lambda x: SalesDataCleaner.bool_or_keep(x),
            'garden':               lambda x: SalesDataCleaner.bool_or_keep(x),
            'swimming_pool_has':    lambda x: SalesDataCleaner.bool_or_keep(x),
            'terrace_area':         lambda x: SalesDataCleaner.float_or_zero(x),
            'land_plot_surface':    lambda x: SalesDataCleaner.float_or_text_to_nan(x),
            'area':                 lambda x: SalesDataCleaner.area_remove_m2(x),
            'price':                lambda x: SalesDataCleaner.price_converter(x)
        }

        columns = columns_types.keys()
        # Null string identifiers (discovered iteratively while improving the process) are defined to be replaced by na
        na_identifiers = ['NA', 'None', 'Not specified', 'NaN', 'NAN']
        # The dataset is read while performing at the same time some basic manipulations
        self.sales_data = pd.read_csv(self.url,  sep=",", dtype=columns_types, skipinitialspace=True, converters=columns_converters, na_values=na_identifiers, low_memory=False)

    @staticmethod
    def price_converter(x):
        #removing non-digit heading and trailiong characters
        x = re.sub(r'\D+$', '', re.sub(r'^\D+', '', x))
        #removing trailing non-digit and dot characters until the last '€' character
        x = re.sub(r'€(.|\D)*$', '', x)
        x = x.replace(',', '')
        #we expect only digits or a dot after replacing commas with an empty string, so we should be able to convert if
        #if not possible we catch the exceptionproperty_subtype
        try:
            return float(x)
        except ValueError:
            return None

    @staticmethod
    #expected boolean are transformed into bool even if originally were strings or numbers
    def bool_or_keep(x):
        output = None
        try:
            if isinstance(x, str):
                if (x == '1') or (x.upper() == 'TRUE'):
                    output = True
                elif (x == '0') or (x.upper() == 'FALSE'):
                    output = False
            elif x.isnumeric():
                if x == 1:
                    output = True
                elif x == 0:
                    output = False
            elif isinstance(x, bool):
                output = x
            return output
        except ValueError:
            return None

    @staticmethod
    def float_or_zero(x):
        try:
            float(x)
            return float(x)
        except ValueError:
            #keeping information of terrace if lost
            return 0 if x in [True, 1, 'True', 'TRUE'] else None
    
    @staticmethod
    #expected float values are returned as None
    def float_or_text_to_nan(x):
        try:
            return float(x)
        #generic value error instead of isistance(x,str) to cover more cases instead of strings only.
        except ValueError:
            return None

    @staticmethod
    #a single integer number is extracted from area to remove the m2 measurement units.
    #this simple method was adopted since no commas were found in area field.
    def area_remove_m2(x):
        try:
            return int(x)
        except ValueError:
            numbers = [int(s) for s in x.split() if s.isdigit()]
            if len(numbers) == 1:
                return float(numbers[0])
            elif len(numbers) > 1:
                return False
            else:
                return None

    def display(self):
        print(self.sales_data)

    def delete_hyperlink_column(self):
        self.sales_data.drop('hyperlink', axis='columns', inplace=True)

    def delete_land_plot_surface_column(self):
        self.sales_data.drop('land_plot_surface', axis='columns', inplace=True)

    def delete_sale_column(self):
        self.sales_data.drop('sale', axis='columns', inplace=True)

    def merge_postcodes_localities_columns(self):
        self.sales_data = self.sales_data.apply(SalesDataCleaner.extract_postcodes, axis='columns')
        self.sales_data.drop('locality', axis='columns', inplace=True)

    @staticmethod
    def extract_postcodes(row):
        if pd.isna(row.postcode):
            legal_belgian_postcode_pattern = '[1-9][0-9][0-9][0-9]'
            extracted_postcodes = re.findall(legal_belgian_postcode_pattern, row.locality)
            row.postcode = extracted_postcodes[0] if len(extracted_postcodes) > 0 else None
        return row

    def add_region_column(self):
        self.sales_data['region'] = self.sales_data['postcode'].map(SalesDataCleaner.to_region)
    
    @staticmethod
    def to_region(postcode):
        if pd.isna(postcode):
            region = None
        else:
            #casting: 'str' -> 'int'
            postcode = int(postcode)
            #'B' -> Brussels-Capital Region
            #'W' -> Walloon Region
            #'F' -> Flemish Region
            if 1000 <= postcode <= 1299:
                region = 'B'
            elif 1300 <= postcode <= 1499 or 4000 <= postcode <= 7999:
                region = 'W'
            else:
                region = 'F'
        return region

    def clean_property_subtype_column(self):
        to_be_deleted_subtypes = ['Wohnung', 'Triplexwohnung', 'Sonstige', 'Loft / �tico', 'Loft / Dachgeschoss', 'Loft / Attic',
               'Gewerbe', 'Etagenwohnung', 'Erdgeschoss', 'Attico', 'Appartamento duplex', 'Apartamento', 'Altbauwohnung',
               'HOUSE_GROUP', 'APARTMENT_GROUP']

        to_be_deleted_filter = self.sales_data['property_subtype'].apply(lambda x: x in to_be_deleted_subtypes)
        self.sales_data.loc[to_be_deleted_filter,'property_subtype'] = None
        
        to_be_deleted_filter = self.sales_data['property_subtype'].apply(lambda x: type(x) in [int, float])
        self.sales_data.loc[to_be_deleted_filter,'property_subtype'] = None
        
        to_be_deleted_filter = self.sales_data['property_subtype'].apply(lambda x: "sqft" in str(x))
        self.sales_data.loc[to_be_deleted_filter,'property_subtype'] = None
    
    def clean_price_column(self):
        to_be_deleted_filter = self.sales_data['price'].apply(lambda x: x == 0.0)
        self.sales_data.loc[to_be_deleted_filter,'price'] = None


    @staticmethod
    def categorize_state(value):
        to_renovate = ['TO_RENOVATE', 'TO_BE_DONE_UP', 'TO_RESTORE', 'old', 'To renovate', 'To be done up', 'To restore']
        good = ['GOOD', 'Good', 'AS_NEW', 'As new']
        renovated = ['JUST_RENOVATED', 'Just renovated']
        new = ['New']
        category = None #default category (corresponds to values = '0')
        if value in to_renovate:
            category = 'to_renovate'
        elif value in good:
            category = 'good'
        elif value in renovated:
            category = 'renovated'
        elif value in  new:
            category = 'new'
        return category
    
    def clean_building_state_column(self):
        self.sales_data['building_state_agg'] = self.sales_data['building_state'].apply(SalesDataCleaner.categorize_state)
        self.sales_data.drop('building_state', axis='columns', inplace=True)
    
    def clean_sale_column(self):
        to_be_deleted_filter = self.sales_data['sale'].str.contains('annuity', na=False)
        to_delete_index = self.sales_data.index[to_be_deleted_filter]
        self.sales_data.drop(to_delete_index, axis='index', inplace = True)
    
    def clean_area_column(self):
        to_be_deleted_filter = self.sales_data['area'].apply(lambda x: x == 0.0)
        self.sales_data.loc[to_be_deleted_filter,'area'] = None

    
    def clean_area_land_surface_columns(self):
        self.sales_data = self.sales_data.apply(SalesDataCleaner.copy_from_land_surface, axis='columns')
    
    def clean_facades_number_column(self):
        to_be_deleted_filter = self.sales_data['facades_number'].apply(lambda x: x == 0 or x > 4)
        self.sales_data.loc[to_be_deleted_filter,'facades_number'] = None

    @staticmethod
    def copy_from_land_surface(row):
        if row.area == 0.0 and row.land_surface > 0.0:
            row.area = row.land_surface
        return row

    def remove_duplicate_records(self):
        self.sales_data.drop_duplicates(subset=['postcode', 'house_is', 'price', 'area'], inplace=True)
        
    
    def remove_na_records(self):
        self.sales_data.dropna(axis=0, inplace=True)
