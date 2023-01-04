# Generated by Django 3.1.2 on 2021-03-18 22:08

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('organization', '0023_adding_sfdc_field'),
    ]

    operations = [
        migrations.RunSQL(
            ''' 
             BEGIN;
               UPDATE organization_organization
             SET sfdc_id = subquery.SFDC_Id
              
              FROM (SELECT id as organization_id, 
                    CASE   	
                    when ID = '461a78ff-97c2-4346-9243-b11298436031' then '0013g000006ArrlAAC'
                    when ID = 'c931d7a9-8af8-469d-a88a-f953dddbf45f' then '0013g000007f6xMAAQ'
                    when ID = 'f311a2ed-ebcf-4de4-b914-2e6c874b5c07' then '0014P00002G9DTgQAN'
                    when ID = 'c931d7a9-8af8-469d-a88a-f953dddbf45f' then '0013g00000C6lbpAAB'
                    when ID = '70f94b26-bcf8-4517-be35-223e97ccadf6' then '0014P00002a1ux8QAA'
                    when ID = '38c28add-6ec8-45a4-80f4-174bb9c8f304' then '0013g000006Bv2EAAS'
                    when ID = '3b219559-a2af-4cd9-a618-0c781c0bad18' then '0013g000009RRtvAAG'
                    when ID = '3d8f1161-a138-46bc-8421-8130519c2d4f' then '0014P00002EIpdfQAD'
                    when ID = 'f3a00f3e-3307-434b-86ba-d36f1bebe6b3' then '0014P00002B5MKWQA3'
                    when ID = '3deedd9c-4654-479c-a39b-6604374af5ef' then '0013g000009TQEmAAO'
                    when ID = '158c46d9-5448-48af-8a38-4108152a45e4' then '0014P00002EIzSjQAL'
                    when ID = 'c56c2a6c-d0f7-4702-8783-c523665a62f5' then '0014P00002DOfsDQAT'
                    when ID = '3e8b7b6a-67b5-4535-8a86-367c1cf20b9d' then '0013g00000AvWIQAA3'
                    when ID = '6381571c-189e-4c91-9b21-5f83af1fa08d' then '0013g00000BXNpSAAX'
                    when ID = '04ff9ccd-5dc4-43ae-b192-1c272284ec8b' then '0013g000009THjxAAG'
                    when ID = '19bca1eb-db62-4f6b-a6f2-2beb63dc1d36' then '0014P00002apNkdQAE'
                    when ID = '2b4dd3be-46f9-41ab-99f5-b9aefa9c7aa9' then '0014P00002EJFjvQAH'
                    when ID = 'd8c5cf24-3716-4483-bd16-6220cc71df69' then '0014P00002aqH1CQAU'
                    when ID = '5ae44393-97fe-4156-8e84-af3cc260f47d' then '0014P000027Ufc4QAC'
                    when ID = 'd27c8f4d-7d77-48bc-8076-478226ab99bb' then '0013g000004SOgNAAW'
                    when ID = '813580f5-5edc-4cfb-bac3-5c0ef0cec7e0' then '0013g000002RTswAAG'
                    when ID = '9ddfcc9b-5875-4dbe-b053-1fc501f052d0' then '0014P00002gApLZQA0'
                    when ID = 'e0ea1159-d366-4a1d-ad76-0018db362aac' then '0013g000006AoqbAAC'
                    when ID = '056d4af1-cb60-48bd-9842-7574677b85ca' then '0013g00000AuGvsAAF'
                    when ID = '20681c55-6043-4fec-83c6-ada2be579ee0' then '0014P00002ZPjwYQAT'
                    when ID = '5b7ede7b-4619-4be8-a7e6-4b4830d8213c' then '0014P00002gATssQAG'
                    when ID = 'f3758049-245d-4f54-81b7-3e0b39ede36b' then '0013g000007g9LnAAI'
                    when ID = 'f68b935b-249e-489e-ab3b-d967a47adcdc' then '0014P00002aqH6LQAU'
                    when ID = 'e9ed5d4c-a446-46b9-8085-c3ba962bc166' then '0013g000004R5ruAAC'
                    when ID = '7b4bb38b-aa86-4bae-9682-c8ea565ab79a' then '0014P00002Qz9IKQAZ'
                    when ID = '6229ae0e-716a-4d01-9f75-c0177328a32a' then '0013g000002QlaIAAS'
                    when ID = 'c63b49f3-d68e-46a6-b4a9-f709623e613e' then '0014P00002aqf9qQAA'
                    when ID = '4b1e0061-59d2-4b70-a36b-f3a8e1155987' then '0014P000027mdRvQAI'
                    when ID = 'e59a78cf-afe0-4b93-aafa-7c71c51e27c3' then '0014P00002gBLuhQAG'
                    when ID = 'df4115ed-0182-4c8f-8778-fd0bfe4871d2' then '0013g000004hBoBAAU'
                    when ID = '8c8dcd81-182c-430f-8267-29684018b4d5' then '0013g00000CQrgCAAT'
                    when ID = 'd408da27-5c73-4cc0-84af-ed8f7c2103df' then '0014P00002f3XCsQAM'
                    when ID = '6c5c5981-47b9-4820-8396-fa3b9a1ae140' then '0013g00000BW40OAAT'
                    when ID = '02f7c089-e085-45fa-9b9a-f06f09e2b028' then '0013g000004SslrAAC'
                    when ID = 'cd9d1607-1e8b-4d73-81fb-b4f3d856ca58' then '0013g000002QQseAAG'
                    when ID = 'bc63fe8c-67d8-4560-97c5-5fa41060578f' then '0014P00002MMaxIQAT'
                    when ID = '769bedab-9f98-46d3-8c0d-c7ae6223767f' then '0013g000006B9lzAAC'
                    when ID = 'bec749c1-0c54-4a0b-bcf4-f559c9d48ad0' then '0014P00002SLCJNQA5' 
                    when ID = '24b5b9d0-75ea-484d-9f20-644cab843a0a' then '0013g000009SfkIAAS'
                    when ID = '2f8ce3ff-de06-4270-85e9-a501d6108181' then '0014P00002aoa0sQAA'
                    when ID = 'ff257507-a2c0-4173-912f-dbefc7347422' then '0013g00000EPPWcAAP' 
                    when ID = '36fdcc4b-789f-4d27-b039-07f651dee3b3' then '0013g000007tNLJAA2'
                    when ID = 'be776ee8-ef31-4a98-871e-7d822b62bf5b' then '0013g000007gJp4AAE'
                    when ID = 'cc1760fd-994b-4cbb-899e-112a02ee51c4' then '0014P00002G9FQKQA3'
                    when ID = '67d532de-bccb-409a-9866-a0e37b9fc174' then '0014P00002Qxt1WQAR'
                    when ID = '675cf69e-827e-4cdb-90de-e4c540fca468' then '0014P000027mdR9QAI'
                    when ID = 'c08fceba-cb5c-4723-afd9-c7d0be08c3cc' then '0014P00002AP9zdQAD'
                    when ID = '235efd52-7adb-457f-a40b-9b4c09232f6c' then '0014P00002ZPpTMQA1'
                    when ID = '1e8e86d8-8252-4b26-bb12-8bf24cc907b3' then '0013g000004SPigAAG'
                    when ID = '8dae7caa-c100-4a2a-a75e-e8f774f45a1d' then '0013g00000ENvC8AAL'
                    when ID = '3268aecc-a36c-4ee4-a244-53b0a3c72f27' then '0014P00002aoWuNQAU'
                    when ID = '205a44ab-6fe6-4863-a6dd-4de041b205b3' then '0013g000007fmu1AAA'
                    when ID = 'c8215bca-1f45-40a4-abbb-f3f24ebfcf9f' then '0014P000027tFMUQA2'
                    when ID = '61cfa7c0-b9ae-4201-9fb5-327e66406203' then '0013g000009RnmMAAS'
                    when ID = '02d8d61c-ff83-4c41-83b0-43802a4ab2de' then '0013g000008pQOJAA2'
                    when ID = 'fd54f6a4-58c5-4bd9-8ecd-77d38579d149' then '0013g000006BmMCAA0'
                    when ID = '4b73ff7d-17f4-41ee-8f25-e856a65e6191' then '0013g00000CQMAjAAP'
                    when ID = '3ed64097-d187-43db-b1a9-f9885df9d7d7' then '0014P00002MNfI9QAL'
                    when ID = 'd1292d94-a6ab-4ec8-ab97-ad052c3f3646' then '0013g00000GLfHUAA1'
                    when ID = '36c24522-495d-43cc-a7e3-e1cb809e3e3d' then '0014P00002B4QklQAF'
                    when ID = '9ffda6f1-070a-4ca0-8800-67d176b58bb9' then '0013g000009QS4YAAW'
                    when ID = '8ecec394-7b3e-4a34-8843-ae599278793b' then '0014P000027nftlQAA'
                    when ID = '1d480203-6aa9-4ff6-8d6f-a308fa472ab5' then '0013g00000GLdejAAD'
                    when ID = '9c4a1521-f932-4147-b463-bcc5aa62544d' then '0013g000004k8RqAAI'
                    when ID = '8606e173-f568-4fc0-992e-40dd2b526c9c' then '0014P00002G8UhRQAV'
                    when ID = 'feffe758-3333-498d-a345-8ddab3847465' then '0013g000002R0ZvAAK'
                    when ID = '62c43cdf-5e2c-4ac8-b89d-912b9cddbe2e' then '0013g00000GLoqiAAD'
                    when ID = 'aa6ac301-817d-47fb-8cc1-7621d4d4683b' then '0014P00002PGSTrQAP'
                    when ID = '5f2f2df6-c287-452c-9e72-f263f67cb820' then '0014P00002PHsIoQAL'
                    when ID = '2a148f0d-c35c-416e-b444-008cd09c3614' then '0013g000004hoMbAAI'
                    when ID = '858d451e-d692-4157-a89e-8fedf8317c71' then '0013g000008p3ryAAA'
                    when ID = 'cb328258-a1d2-4b40-9bb6-dd566709b4a3' then '0013g000009RXL4AAO'
                    when ID = '8337f156-1b31-4da3-9f14-01f7189e7cd2' then '0014P000027T8yIQAS' 
                    when ID = '3614aaba-06ff-48b6-87cc-cbafad8c2d30' then '0013g000009R4a3AAC'
                    when ID = '3b4a594d-3534-4bc8-8c81-e0097fd48ca1' then '0013g00000C5yNqAAJ'
                    when ID = '175934c1-a985-4a6d-8183-496123dd8249' then '0014P00002APA0kQAH'
                    when ID = '8222df75-0a88-4286-b5ea-f1d9733bedaa' then '0013g00000AGopeAAD'
                    when ID = 'a01179aa-f25a-4c97-9b7c-539282c80080' then '0014P00002AaJXkQAN'
                    when ID = '8fb80c3c-b974-4809-b3d0-01db97b2c0d7' then '0013g000006CCwBAAW'
                    when ID = 'cb6c9051-ce34-4927-b2a7-a25ffcfcb0c2' then '0013g000009RD8TAAW'
                    when ID = '0998e4e6-be2d-4abc-b042-df3e745ff343' then '0013g000008odsWAAQ'
                    when ID = '56290371-192b-4ee0-ab47-cfefcfe0bdaf' then '0013g000008oTg2AAE'
                    when ID = '656f0820-fa2e-4963-a557-892b09de2d5d' then '0014P00002MM2hDQAT'
                    when ID = '78316ca1-ef4f-47ac-9b6f-92f825dfbec3' then '0013g00000EMeHLAA1'
                    when ID = '04dc8551-22ff-4597-8343-ecd75f2384f8' then '0014P000027n2MpQAI'
                    when ID = '31760830-bfc5-402f-88d4-0270b8d0920c' then '0013g000007fA8YAAU'
                    when ID = '9e28b635-413b-4714-9d8e-b79d7ad06679' then '0013g000008olx9AAA'
                    when ID = 'e3016309-6f9a-4180-9b93-e93a7f9d63e0' then '0014P00002DOiOCQA1'
                    when ID ='7cb538e1-1ba0-4c0c-a5dd-46fdb48bf530' then '0013g00000AvorYAAR'
                    when ID ='7df2a737-7917-42ca-b504-3c028bda616b' then '0013g000009Snh0AAC'
                    when ID ='1191e6d4-8c72-4160-b9bb-242b100b7e01' then '0013g00000COrIGAA1'
                    when ID ='08f80556-248c-4b91-920c-71f16428ccae' then '0013g00000BXcG2AAL'
                    when ID ='0bba4e06-85af-49aa-a84d-2ada2fa0443e' then '0014P00002eKKUnQAO'
                    when ID ='988a249d-3f84-4373-8196-d96ea58b53c2' then '0013g00000GKtoaAAD'
                    when ID ='b8f7a58e-2301-4b33-bdd9-1e0a7c7afd65' then '0014P00002MLJOlQAP'
                    when ID ='af50095c-178d-4f62-a210-eeb4a8060925' then '0014P00002akZPpQAM'
                    when ID ='155a0525-167e-4983-88f5-a18b52f213d5' then '0014P00002aL0LPQA0'
                    when ID ='3e948279-87a1-4ffa-a8ab-e748c1ca1218' then '0013g000007v3LtAAI'
                    when ID ='e67fd4a7-5c1c-4fe1-ab45-bd29d33bc73c' then '0014P00002EJRYPQA5'
                    when ID ='b001d7fc-1b33-499c-a4e4-d31d3f0873fc' then '0013g00000EPjF0AAL'
                    when ID ='8dca8d53-b8f7-4c3b-a3d8-6fd00b75f137' then '0013g000007v4PKAAY'
                    ELSE null
                END AS SFDC_Id

              FROM  organization_organization
              WHERE  id IN (
                    '461a78ff-97c2-4346-9243-b11298436031',
                    'c931d7a9-8af8-469d-a88a-f953dddbf45f',
                    'f311a2ed-ebcf-4de4-b914-2e6c874b5c07',
                    'c931d7a9-8af8-469d-a88a-f953dddbf45f',
                    '70f94b26-bcf8-4517-be35-223e97ccadf6',
                    '38c28add-6ec8-45a4-80f4-174bb9c8f304',
                    '3b219559-a2af-4cd9-a618-0c781c0bad18',
                    '3d8f1161-a138-46bc-8421-8130519c2d4f',
                    'f3a00f3e-3307-434b-86ba-d36f1bebe6b3',
                    '3deedd9c-4654-479c-a39b-6604374af5ef',
                    '158c46d9-5448-48af-8a38-4108152a45e4',
                    'c56c2a6c-d0f7-4702-8783-c523665a62f5',
                    '3e8b7b6a-67b5-4535-8a86-367c1cf20b9d',
                    '6381571c-189e-4c91-9b21-5f83af1fa08d',
                    '04ff9ccd-5dc4-43ae-b192-1c272284ec8b', 
                    '19bca1eb-db62-4f6b-a6f2-2beb63dc1d36', 
                    '2b4dd3be-46f9-41ab-99f5-b9aefa9c7aa9', 
                    'd8c5cf24-3716-4483-bd16-6220cc71df69', 
                    '5ae44393-97fe-4156-8e84-af3cc260f47d', 
                    'd27c8f4d-7d77-48bc-8076-478226ab99bb', 
                    '813580f5-5edc-4cfb-bac3-5c0ef0cec7e0',
                    '9ddfcc9b-5875-4dbe-b053-1fc501f052d0', 
                    'e0ea1159-d366-4a1d-ad76-0018db362aac', 
                    '056d4af1-cb60-48bd-9842-7574677b85ca', 
                    '20681c55-6043-4fec-83c6-ada2be579ee0', 
                    '5b7ede7b-4619-4be8-a7e6-4b4830d8213c', 
                    'f3758049-245d-4f54-81b7-3e0b39ede36b', 
                    'f68b935b-249e-489e-ab3b-d967a47adcdc',
                    'e9ed5d4c-a446-46b9-8085-c3ba962bc166', 
                    '7b4bb38b-aa86-4bae-9682-c8ea565ab79a', 
                    '6229ae0e-716a-4d01-9f75-c0177328a32a', 
                    'c63b49f3-d68e-46a6-b4a9-f709623e613e', 
                    '4b1e0061-59d2-4b70-a36b-f3a8e1155987',
                    'e59a78cf-afe0-4b93-aafa-7c71c51e27c3', 
                    'df4115ed-0182-4c8f-8778-fd0bfe4871d2', 
                    '8c8dcd81-182c-430f-8267-29684018b4d5', 
                    'd408da27-5c73-4cc0-84af-ed8f7c2103df', 
                    '6c5c5981-47b9-4820-8396-fa3b9a1ae140', 
                    '02f7c089-e085-45fa-9b9a-f06f09e2b028',
                    'cd9d1607-1e8b-4d73-81fb-b4f3d856ca58',
                    'bc63fe8c-67d8-4560-97c5-5fa41060578f',
                    '769bedab-9f98-46d3-8c0d-c7ae6223767f',
                    'bec749c1-0c54-4a0b-bcf4-f559c9d48ad0', 
                    '24b5b9d0-75ea-484d-9f20-644cab843a0a',
                    '2f8ce3ff-de06-4270-85e9-a501d6108181',
                    'ff257507-a2c0-4173-912f-dbefc7347422', 
                    '36fdcc4b-789f-4d27-b039-07f651dee3b3',
                    'be776ee8-ef31-4a98-871e-7d822b62bf5b',
                    'cc1760fd-994b-4cbb-899e-112a02ee51c4',  
                    '67d532de-bccb-409a-9866-a0e37b9fc174',
                    '675cf69e-827e-4cdb-90de-e4c540fca468',
                    'c08fceba-cb5c-4723-afd9-c7d0be08c3cc', 
                    '235efd52-7adb-457f-a40b-9b4c09232f6c', 
                    '1e8e86d8-8252-4b26-bb12-8bf24cc907b3', 
                    '8dae7caa-c100-4a2a-a75e-e8f774f45a1d', 
                    '3268aecc-a36c-4ee4-a244-53b0a3c72f27', 
                    '205a44ab-6fe6-4863-a6dd-4de041b205b3', 
                    'c8215bca-1f45-40a4-abbb-f3f24ebfcf9f', 
                    '61cfa7c0-b9ae-4201-9fb5-327e66406203', 
                    '02d8d61c-ff83-4c41-83b0-43802a4ab2de', 
                    'fd54f6a4-58c5-4bd9-8ecd-77d38579d149', 
                    '4b73ff7d-17f4-41ee-8f25-e856a65e6191',
                    '3ed64097-d187-43db-b1a9-f9885df9d7d7',
                    'd1292d94-a6ab-4ec8-ab97-ad052c3f3646', 
                    '36c24522-495d-43cc-a7e3-e1cb809e3e3d', 
                    '9ffda6f1-070a-4ca0-8800-67d176b58bb9', 
                    '8ecec394-7b3e-4a34-8843-ae599278793b', 
                    '1d480203-6aa9-4ff6-8d6f-a308fa472ab5', 
                    '9c4a1521-f932-4147-b463-bcc5aa62544d', 
                    '8606e173-f568-4fc0-992e-40dd2b526c9c', 
                    'feffe758-3333-498d-a345-8ddab3847465', 
                    '62c43cdf-5e2c-4ac8-b89d-912b9cddbe2e', 
                    'aa6ac301-817d-47fb-8cc1-7621d4d4683b', 
                    '5f2f2df6-c287-452c-9e72-f263f67cb820', 
                    '2a148f0d-c35c-416e-b444-008cd09c3614',
                    '858d451e-d692-4157-a89e-8fedf8317c71',
                    'cb328258-a1d2-4b40-9bb6-dd566709b4a3', 
                    '8337f156-1b31-4da3-9f14-01f7189e7cd2',
                    '3614aaba-06ff-48b6-87cc-cbafad8c2d30',
                    '3b4a594d-3534-4bc8-8c81-e0097fd48ca1', 
                    '175934c1-a985-4a6d-8183-496123dd8249', 
                    '8222df75-0a88-4286-b5ea-f1d9733bedaa', 
                    'a01179aa-f25a-4c97-9b7c-539282c80080', 
                    '8fb80c3c-b974-4809-b3d0-01db97b2c0d7', 
                    'cb6c9051-ce34-4927-b2a7-a25ffcfcb0c2', 
                    '0998e4e6-be2d-4abc-b042-df3e745ff343', 
                    '56290371-192b-4ee0-ab47-cfefcfe0bdaf', 
                    '656f0820-fa2e-4963-a557-892b09de2d5d', 
                    '78316ca1-ef4f-47ac-9b6f-92f825dfbec3', 
                    '04dc8551-22ff-4597-8343-ecd75f2384f8', 
                    '31760830-bfc5-402f-88d4-0270b8d0920c', 
                    '9e28b635-413b-4714-9d8e-b79d7ad06679', 
                    'e3016309-6f9a-4180-9b93-e93a7f9d63e0',
                    '7cb538e1-1ba0-4c0c-a5dd-46fdb48bf530',
                    '7df2a737-7917-42ca-b504-3c028bda616b',
                    '1191e6d4-8c72-4160-b9bb-242b100b7e01', 
                    '08f80556-248c-4b91-920c-71f16428ccae', 
                    '0bba4e06-85af-49aa-a84d-2ada2fa0443e', 
                    '988a249d-3f84-4373-8196-d96ea58b53c2', 
                    'b8f7a58e-2301-4b33-bdd9-1e0a7c7afd65', 
                    'af50095c-178d-4f62-a210-eeb4a8060925',
                    '155a0525-167e-4983-88f5-a18b52f213d5', 
                    '3e948279-87a1-4ffa-a8ab-e748c1ca1218', 
                    'e67fd4a7-5c1c-4fe1-ab45-bd29d33bc73c', 
                    'b001d7fc-1b33-499c-a4e4-d31d3f0873fc', 
                    '8dca8d53-b8f7-4c3b-a3d8-6fd00b75f137'
               )) AS subquery
               
              WHERE  id = subquery.organization_id;
            COMMIT;
        '''
        )
    ]
